# Chat Parser De-Hardcoding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the demo-only assumptions in `service/backend/app/services/chat_parser.py`: the hardcoded 2025 sep/oct/nov map (`_MONTH_RANGES`) and the "books"-only semantic scope keywords (`_SEMANTIC_SCOPE_KEYWORDS`). Replace with (a) a full 12-month table plus configurable year sourced from actual review-date range in Postgres, and (b) a configurable list of semantic-scope keywords with a working default derived from `KNOWN_LABELS`.

**Architecture:**
- Add a new module `app/services/ru_months.py` with the full stem→(month, num-days) map for all 12 Russian months. Use `calendar.monthrange` to compute end-of-month correctly (handles Feb + leap years).
- Add a small helper `app/services/date_context.py` that computes the "default year" for chat parsing: prefer settings override, else derive from the max `review_date` in Postgres (via `get_pool()`), else fall back to `datetime.date.today().year`. Cache the value per-process with a manual refresh method.
- Add `Settings.chat_semantic_scope_keywords: list[str]` (defaults to a broader set derived from labels/domain) and `Settings.chat_default_year: int | None` (explicit override).
- `chat_parser.py`: `_mentioned_month_ranges` and `_parse_month_range` become instance methods reading from `ru_months` + the resolved default year. `_has_semantic_scope` reads from settings.
- Preserve the existing single test (`test_chat_rules_compare_october_with_september_uses_october_as_current_period`) by pinning the default year via env in that test (or by having the test's month resolve deterministically from the resolved year).

**Tech Stack:** Python 3.11 stdlib (`calendar`), pydantic-settings 2.7, psycopg pool (optional dependency — the derivation gracefully degrades when Postgres is offline).

## Global Constraints

- Comments and user-facing strings in Russian; identifiers in English.
- The `_MONTH_RANGES` dict and 5-keyword `_SEMANTIC_SCOPE_KEYWORDS` tuple must be **removed** — not shadowed. No dead code left behind.
- The LLM prompt still needs to reference the current year explicitly (rule #6 in `_build_llm_prompt`). Update that too, not just the rule-based path.
- Existing behaviour on `"сравни октябрь с сентябрем"` must remain: intent `period_comparison`, `date_from`/`date_to` = October of the resolved default year. The one existing chat-parser test in `test_contracts.py` must still pass (adjust the assertion year if you change the default-year source, but keep the test's intent).
- Rule-based fallback must work without Postgres (offline dev). If Postgres is unavailable, default year comes from settings override or `date.today().year`.

---

### Task 1: Add full Russian months module with tests

**Files:**
- Create: `service/backend/app/services/ru_months.py`
- Create: `service/tests/test_ru_months.py`

**Interfaces:**
- Consumes: `calendar.monthrange` from stdlib.
- Produces:
  - `RU_MONTH_STEMS: dict[str, int]` — stem → month number (1..12). Includes at minimum: `"январ"`, `"феврал"`, `"март"`, `"апрел"`, `"май"` (5, exact), `"июн"`, `"июл"`, `"август"`, `"сентябр"`, `"октябр"`, `"ноябр"`, `"декабр"`.
  - `mentioned_month_numbers(text: str) -> list[int]` — returns unique month numbers found in `text.lower()`, preserving stem order in the dict.
  - `month_range(year: int, month: int) -> tuple[str, str]` — returns (`"YYYY-MM-01"`, `"YYYY-MM-DD"` with correct last day).

- [ ] **Step 1: Write the failing test**

Create `service/tests/test_ru_months.py`:

```python
from app.services.ru_months import RU_MONTH_STEMS, mentioned_month_numbers, month_range


def test_ru_month_stems_covers_all_12_months() -> None:
    assert sorted(RU_MONTH_STEMS.values()) == list(range(1, 13))


def test_mentioned_month_numbers_finds_multiple_in_order() -> None:
    assert mentioned_month_numbers("сравни октябрь с сентябрем") == [9, 10]


def test_mentioned_month_numbers_empty_when_no_month() -> None:
    assert mentioned_month_numbers("покажи топ проблем") == []


def test_month_range_regular_month() -> None:
    assert month_range(2025, 10) == ("2025-10-01", "2025-10-31")


def test_month_range_february_leap_year() -> None:
    assert month_range(2024, 2) == ("2024-02-01", "2024-02-29")


def test_month_range_february_non_leap_year() -> None:
    assert month_range(2025, 2) == ("2025-02-01", "2025-02-28")


def test_month_range_short_may_stem_does_not_false_match() -> None:
    # "май" — короткий стем, не должен ловить, например, "майка".
    numbers = mentioned_month_numbers("купил майку летом")
    assert 5 not in numbers
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd service && pytest tests/test_ru_months.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement ru_months module**

Create `service/backend/app/services/ru_months.py`:

```python
"""Русские месяцы: стемы для распознавания в тексте и диапазоны дат."""

import calendar
import re


# Стемы месяцев в порядке от января к декабрю. Стем — минимальный корень,
# по которому детектируется месяц в свободном тексте (напр. "октябр" ловит
# "октябрь", "октябре", "октября", "октябрём").
RU_MONTH_STEMS: dict[str, int] = {
    "январ": 1,
    "феврал": 2,
    "март": 3,
    "апрел": 4,
    "май": 5,   # "май" — только точное вхождение слова, см. _MAY_PATTERN
    "июн": 6,
    "июл": 7,
    "август": 8,
    "сентябр": 9,
    "октябр": 10,
    "ноябр": 11,
    "декабр": 12,
}


# Для короткого стема "май" используем регекс с границами слова,
# чтобы не срабатывать на "майка", "маяк" и т.п.
_MAY_PATTERN = re.compile(r"\bма[йяею]\b", re.IGNORECASE)


def mentioned_month_numbers(text: str) -> list[int]:
    """Возвращает уникальные номера месяцев, упомянутых в тексте, в порядке возрастания."""
    lowered = text.lower()
    found: set[int] = set()

    for stem, number in RU_MONTH_STEMS.items():
        if number == 5:
            if _MAY_PATTERN.search(lowered):
                found.add(5)
            continue
        if stem in lowered:
            found.add(number)

    return sorted(found)


def month_range(year: int, month: int) -> tuple[str, str]:
    """Возвращает пару (YYYY-MM-01, YYYY-MM-<last_day>) для указанного месяца."""
    _, last_day = calendar.monthrange(year, month)
    return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last_day:02d}"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd service && pytest tests/test_ru_months.py -v
```

Expected: all seven tests PASS.

- [ ] **Step 5: Commit**

```bash
git add service/backend/app/services/ru_months.py service/tests/test_ru_months.py
git commit -m "feat(services): add full Russian months stem table with month_range helper"
```

---

### Task 2: Add date context resolver with tests

**Files:**
- Create: `service/backend/app/services/date_context.py`
- Create: `service/tests/test_date_context.py`
- Modify: `service/backend/app/core/config.py`

**Interfaces:**
- Consumes: `Settings.chat_default_year: int | None`, `app.core.db.get_pool()`.
- Produces:
  - `class DateContext` with method `default_year() -> int` and `refresh() -> None`. Resolution order: settings override → max(review_date).year via pool → `date.today().year`.
  - Singleton accessor `get_date_context() -> DateContext`.

- [ ] **Step 1: Add chat_default_year to Settings**

In `service/backend/app/core/config.py`, add after `chat_parser_mode: str = "auto"`:

```python
    chat_default_year: int | None = None
    chat_semantic_scope_keywords: list[str] = [
        "книг", "облож", "страниц", "учебник", "роман",
        "переплёт", "переплет", "иллюстрац",
    ]
```

Also add a validator alongside the CORS one (or add one if the CORS plan hasn't been applied yet):

```python
    @field_validator("chat_semantic_scope_keywords", mode="before")
    @classmethod
    def _split_scope_keywords(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value
```

Add the import if not already present:

```python
from pydantic import field_validator
```

- [ ] **Step 2: Write the failing test**

Create `service/tests/test_date_context.py`:

```python
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.core import db
from app.services import date_context as dc_module


def test_default_year_from_settings_override(monkeypatch) -> None:
    monkeypatch.setattr(dc_module, "_context", None)
    monkeypatch.setattr(
        dc_module,
        "get_settings",
        lambda: SimpleNamespace(chat_default_year=2027),
    )
    monkeypatch.setattr(db, "_pool", None)

    assert dc_module.get_date_context().default_year() == 2027


def test_default_year_from_pool_when_no_override(monkeypatch) -> None:
    monkeypatch.setattr(dc_module, "_context", None)
    monkeypatch.setattr(
        dc_module,
        "get_settings",
        lambda: SimpleNamespace(chat_default_year=None),
    )

    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchone.return_value = {"max_year": 2024}
    conn = MagicMock()
    conn.__enter__.return_value = conn
    conn.cursor.return_value = cursor
    pool = MagicMock()
    pool.connection.return_value = conn

    monkeypatch.setattr(db, "_pool", pool)

    assert dc_module.get_date_context().default_year() == 2024


def test_default_year_falls_back_to_today(monkeypatch) -> None:
    monkeypatch.setattr(dc_module, "_context", None)
    monkeypatch.setattr(
        dc_module,
        "get_settings",
        lambda: SimpleNamespace(chat_default_year=None),
    )
    monkeypatch.setattr(db, "_pool", None)

    from datetime import date
    assert dc_module.get_date_context().default_year() == date.today().year


def test_refresh_reloads_year_from_pool(monkeypatch) -> None:
    monkeypatch.setattr(dc_module, "_context", None)
    monkeypatch.setattr(
        dc_module,
        "get_settings",
        lambda: SimpleNamespace(chat_default_year=None),
    )
    monkeypatch.setattr(db, "_pool", None)

    ctx = dc_module.get_date_context()
    first = ctx.default_year()
    ctx.refresh()
    assert ctx.default_year() == first
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd service && pytest tests/test_date_context.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 4: Implement date_context**

Create `service/backend/app/services/date_context.py`:

```python
"""Резолвер года по умолчанию для парсинга дат в chat-запросах."""

from datetime import date

from app.core.config import get_settings
from app.core.db import get_pool


class DateContext:
    def __init__(self) -> None:
        self._cached_year: int | None = None

    def default_year(self) -> int:
        if self._cached_year is not None:
            return self._cached_year

        settings = get_settings()
        if settings.chat_default_year is not None:
            self._cached_year = int(settings.chat_default_year)
            return self._cached_year

        year_from_db = self._query_max_review_year()
        if year_from_db is not None:
            self._cached_year = year_from_db
            return self._cached_year

        self._cached_year = date.today().year
        return self._cached_year

    def refresh(self) -> None:
        self._cached_year = None

    def _query_max_review_year(self) -> int | None:
        pool = get_pool()
        if pool is None:
            return None
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT EXTRACT(YEAR FROM MAX(review_date))::int AS max_year FROM reviews;"
                    )
                    row = cur.fetchone()
        except Exception:  # noqa: BLE001
            return None
        if not row:
            return None
        value = row.get("max_year") if isinstance(row, dict) else row[0]
        return int(value) if value else None


_context: DateContext | None = None


def get_date_context() -> DateContext:
    global _context
    if _context is None:
        _context = DateContext()
    return _context
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd service && pytest tests/test_date_context.py -v
```

Expected: all four tests PASS.

- [ ] **Step 6: Commit**

```bash
git add service/backend/app/services/date_context.py service/tests/test_date_context.py service/backend/app/core/config.py
git commit -m "feat(chat): add DateContext resolver (settings > db > today) and scope keywords setting"
```

---

### Task 3: De-hardcode chat_parser.py

**Files:**
- Modify: `service/backend/app/services/chat_parser.py`
- Modify: `service/tests/test_contracts.py`
- Modify: `service/backend/.env.docker.example`
- Modify: `service/backend/.env.example`

**Interfaces:**
- Consumes:
  - `RU_MONTH_STEMS`, `mentioned_month_numbers`, `month_range` from `app.services.ru_months`.
  - `get_date_context` from `app.services.date_context`.
  - `Settings.chat_semantic_scope_keywords` from Task 2.
- Produces: `ChatParser` with no hardcoded years, months, or scope keywords. All month/year resolution happens through `ru_months` + `DateContext`; scope keywords read from settings.

- [ ] **Step 1: Rewrite chat_parser.py**

Replace `service/backend/app/services/chat_parser.py` with:

```python
import json
import re
from openai import OpenAI

from app.core.config import get_settings
from app.domain.labels import KNOWN_LABELS, find_labels_in_text
from app.schemas.query import AnswerMode, ChatAskRequest, GroupBy, Intent, ParsedQuery, QuerySource, ReviewFilters, ToolName
from app.services.date_context import get_date_context
from app.services.ru_months import mentioned_month_numbers, month_range


class ChatParser:
    """Chat parser для MVP.

    Если задан OPENAI_API_KEY, сначала пробует LLM → ParsedQuery.
    Если ключа нет или LLM вернул невалидный JSON, использует rule-based fallback.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.date_context = get_date_context()
        self.last_parse_method = "not_started"
        self.last_parse_error: str | None = None

    def parse(self, request: ChatAskRequest) -> ParsedQuery:
        self.last_parse_error = None
        if self.settings.chat_parser_mode != "rules" and self.settings.openai_api_key:
            parsed = self._parse_with_llm(request)
            if parsed is not None:
                self.last_parse_method = "llm"
                return parsed
            self.last_parse_method = "rules_after_llm_failure"
        elif self.settings.chat_parser_mode == "rules":
            self.last_parse_method = "rules_forced"
        else:
            self.last_parse_method = "rules_no_api_key"

        return self._parse_with_rules(request)

    def _parse_with_rules(self, request: ChatAskRequest) -> ParsedQuery:
        text = request.message.lower()

        labels = find_labels_in_text(text)
        date_from, date_to = self._parse_month_range(text)
        keyword = self._parse_keyword(text)
        group_by = self._parse_group_by(text)
        min_rating, max_rating = self._parse_rating_filters(text)

        intent = self._parse_intent(text, keyword)
        tools = self._tools_for_intent(intent, text)
        answer_mode = AnswerMode.TEMPLATE

        if ToolName.QDRANT in tools:
            answer_mode = AnswerMode.LLM

        if request.force_answer_mode:
            answer_mode = AnswerMode(request.force_answer_mode)

        query = ParsedQuery(
            source=QuerySource.CHAT,
            intent=intent,
            filters=ReviewFilters(
                date_from=date_from,
                date_to=date_to,
                labels=labels,
                keyword=keyword,
                min_rating=min_rating,
                max_rating=max_rating,
            ),
            group_by=group_by,
            semantic_query=request.message,
            tools=tools,
            answer_mode=answer_mode,
        )
        return self._normalize_query(query, request.message)

    def _parse_with_llm(self, request: ChatAskRequest) -> ParsedQuery | None:
        client = OpenAI(api_key=self.settings.openai_api_key)
        prompt = self._build_llm_prompt(request.message)

        try:
            response = client.responses.create(
                model=self.settings.openai_model,
                input=prompt,
            )
            data = json.loads(response.output_text)
            data["source"] = QuerySource.CHAT
            data["semantic_query"] = data.get("semantic_query") or request.message

            if request.force_answer_mode:
                data["answer_mode"] = request.force_answer_mode

            query = ParsedQuery.model_validate(data)
            query.filters.labels = [label for label in query.filters.labels if label in KNOWN_LABELS]
            return self._normalize_query(query, request.message)
        except Exception as exc:  # noqa: BLE001
            self.last_parse_error = type(exc).__name__
            return None

    def _build_llm_prompt(self, message: str) -> str:
        labels_json = json.dumps(KNOWN_LABELS, ensure_ascii=False)
        year = self.date_context.default_year()
        return f"""
Ты parser для сервиса аналитики отзывов маркетплейса.
Преобразуй вопрос пользователя в JSON ParsedQuery. Верни только JSON без markdown.

Доступные labels:
{labels_json}

Допустимые intent:
- count_by_problem
- top_problems
- problem_dynamics
- review_samples
- period_comparison
- problem_share
- problem_growth
- label_cooccurrence
- keyword_search
- positive_vs_problem
- top_products_by_problem
- review_examples

Допустимые tools: postgres, qdrant.
Правила:
1. Для точных чисел, долей, топов, динамики и сравнения периодов используй postgres.
2. Для "похожие отзывы", "примеры", "что именно пишут", "на что жалуются" используй qdrant.
   Если нужны и числа, и примеры, используй оба tools.
3. Для объяснений, выводов и рекомендаций ставь answer_mode = "llm".
4. Положительный / нейтральный отзыв используй только если пользователь явно спрашивает про позитив.
5. Не придумывай brand/product/category, если их нет в вопросе.
   Semantic scope (например, "книги", "обложки", "страницы") — это НЕ обязательно значение
   `filters.category`; добавь `qdrant` в tools и положи исходный вопрос в `semantic_query`.
6. Если месяц указан без года, считай текущим годом {year}.
   Диапазон месяца: с первого по последний день (учитывая високосный год для февраля).
7. Если пользователь спрашивает про "рваные", "помятые", "обложки", относись к проблемам качества товара.
8. "Главные проблемы у книг" → tools = ["postgres", "qdrant"], intent = "top_problems", answer_mode = "llm".
9. "Топ товаров", "товары с проблемами", "артикулы с жалобами" → intent = "top_products_by_problem".
10. Для "почему", "объясни", "с примерами" вместе с топами/долями → tools = ["postgres", "qdrant"], answer_mode = "llm".

Форма JSON:
{{
  "source": "chat",
  "intent": "review_examples",
  "filters": {{
    "date_from": null,
    "date_to": null,
    "labels": [],
    "keyword": null,
    "category": null,
    "brand": null,
    "product_id": null,
    "product_name": null,
    "min_rating": null,
    "max_rating": null
  }},
  "group_by": null,
  "semantic_query": "{message}",
  "tools": ["qdrant"],
  "answer_mode": "llm",
  "limit": 20
}}

Вопрос пользователя:
{message}
""".strip()

    def _parse_intent(self, text: str, keyword: str | None) -> Intent:
        if ("товар" in text or "продукт" in text or "артикул" in text) and (
            "топ" in text or "главн" in text or "самые" in text or "больше всего" in text
        ):
            return Intent.TOP_PRODUCTS_BY_PROBLEM
        if "похож" in text or "примеры" in text or "пример" in text or "что пишут" in text or "на что жал" in text:
            return Intent.REVIEW_EXAMPLES
        if keyword or "найди" in text or "поиск" in text:
            return Intent.KEYWORD_SEARCH
        if "покажи отзывы" in text or "тексты отзыв" in text:
            return Intent.REVIEW_SAMPLES
        if "вместе" in text or "связана" in text or "связано" in text or "совмест" in text:
            return Intent.LABEL_COOCCURRENCE
        if "доля" in text or "процент" in text or "структур" in text:
            return Intent.PROBLEM_SHARE
        if "полож" in text and ("проблем" in text or "нейтрал" in text):
            return Intent.POSITIVE_VS_PROBLEM
        if "динамик" in text or "по дня" in text or "по недел" in text or "по месяц" in text:
            return Intent.PROBLEM_DYNAMICS
        if "сравн" in text or "относительно" in text or "что вырос" in text or "что упал" in text or "стало хуже" in text:
            return Intent.PERIOD_COMPARISON
        if "раст" in text or "вырос" in text or "сниз" in text:
            return Intent.PROBLEM_GROWTH
        if "топ" in text or "главн" in text or "самые част" in text:
            return Intent.TOP_PROBLEMS
        return Intent.COUNT_BY_PROBLEM

    def _tools_for_intent(self, intent: Intent, text: str) -> list[ToolName]:
        wants_examples = any(marker in text for marker in ("пример", "что пишут", "почему", "объясни", "причин"))
        aggregate_intents = {
            Intent.TOP_PROBLEMS,
            Intent.TOP_PRODUCTS_BY_PROBLEM,
            Intent.PROBLEM_SHARE,
            Intent.PERIOD_COMPARISON,
            Intent.PROBLEM_GROWTH,
            Intent.PROBLEM_DYNAMICS,
        }
        if wants_examples and intent in aggregate_intents:
            return [ToolName.POSTGRES, ToolName.QDRANT]
        if self._has_semantic_scope(text):
            return [ToolName.POSTGRES, ToolName.QDRANT]
        if intent == Intent.REVIEW_EXAMPLES:
            if "сколько" in text or "доля" in text or "динамик" in text or "топ" in text:
                return [ToolName.POSTGRES, ToolName.QDRANT]
            return [ToolName.QDRANT]
        return [ToolName.POSTGRES]

    def _normalize_query(self, query: ParsedQuery, message: str) -> ParsedQuery:
        query = self._normalize_semantic_scope(query, message)
        return self._normalize_month_comparison(query, message)

    def _normalize_semantic_scope(self, query: ParsedQuery, message: str) -> ParsedQuery:
        text = message.lower()
        category = query.filters.category
        category_is_semantic = bool(category and self._has_semantic_scope(category.lower()))

        if self._has_semantic_scope(text) or category_is_semantic:
            query.filters.category = None if category_is_semantic else category
            query.semantic_query = message
            query.tools = self._merge_tools(query.tools, [ToolName.POSTGRES, ToolName.QDRANT])
            if query.intent in {Intent.TOP_PROBLEMS, Intent.REVIEW_EXAMPLES, Intent.REVIEW_SAMPLES}:
                query.answer_mode = AnswerMode.LLM

        return query

    def _normalize_month_comparison(self, query: ParsedQuery, message: str) -> ParsedQuery:
        if query.intent not in {Intent.PERIOD_COMPARISON, Intent.PROBLEM_GROWTH, Intent.PROBLEM_GROWTH_ANALYSIS}:
            return query

        month_numbers = mentioned_month_numbers(message)
        if len(month_numbers) < 2:
            return query

        year = self.date_context.default_year()
        # SQLBuilder trait: date_from/date_to = "текущий" период, сравнивается с предыдущим
        # равной длины. Для "сравни октябрь с сентябрём" текущий период — октябрь.
        query.filters.date_from, query.filters.date_to = month_range(year, month_numbers[-1])
        return query

    def _has_semantic_scope(self, text: str) -> bool:
        return any(keyword in text for keyword in self.settings.chat_semantic_scope_keywords)

    def _merge_tools(self, current: list[ToolName], extra: list[ToolName]) -> list[ToolName]:
        merged = list(current)
        for tool in extra:
            if tool not in merged:
                merged.append(tool)
        return merged

    def _parse_month_range(self, text: str) -> tuple[str | None, str | None]:
        month_numbers = mentioned_month_numbers(text)
        if not month_numbers:
            return None, None
        year = self.date_context.default_year()
        return month_range(year, month_numbers[0])

    def _parse_group_by(self, text: str) -> GroupBy | None:
        if "по дня" in text:
            return GroupBy.DAY
        if "по недел" in text:
            return GroupBy.WEEK
        if "по месяц" in text:
            return GroupBy.MONTH
        return None

    def _parse_keyword(self, text: str) -> str | None:
        quoted = re.search(r'["«](.+?)["»]', text)
        if quoted:
            return quoted.group(1).strip()

        for marker in ("со словом", "слово", "фраза", "где пишут", "где есть"):
            if marker in text:
                tail = text.split(marker, 1)[1].strip(" :—-'")
                if tail:
                    return tail[:80]
        return None

    def _parse_rating_filters(self, text: str) -> tuple[int | None, int | None]:
        if "низк" in text and "рейтинг" in text:
            return None, 2
        if "негатив" in text or "плохие оценки" in text:
            return None, 2
        match = re.search(r"(?:рейтинг|оценк[аи])\s*(?:<=|до|ниже)\s*([1-5])", text)
        if match:
            return None, int(match.group(1))
        match = re.search(r"(?:рейтинг|оценк[аи])\s*(?:>=|от|выше)\s*([1-5])", text)
        if match:
            return int(match.group(1)), None
        return None, None
```

- [ ] **Step 2: Update existing chat-parser test to pin the year**

Replace the `test_chat_rules_compare_october_with_september_uses_october_as_current_period` test (lines 68-75) in `service/tests/test_contracts.py` with:

```python
def test_chat_rules_compare_october_with_september_uses_october_as_current_period(monkeypatch) -> None:
    monkeypatch.setenv("CHAT_DEFAULT_YEAR", "2025")

    from app.core.config import get_settings
    get_settings.cache_clear()

    from app.services import date_context as dc_module
    dc_module._context = None  # noqa: SLF001

    parser = ChatParser()

    query = parser._parse_with_rules(ChatAskRequest(message="сравни октябрь с сентябрем"))  # noqa: SLF001

    assert query.intent == "period_comparison"
    assert query.filters.date_from == "2025-10-01"
    assert query.filters.date_to == "2025-10-31"
```

- [ ] **Step 3: Add tests for new behaviour**

Append to `service/tests/test_contracts.py`:

```python
def test_chat_rules_recognises_all_month_stems(monkeypatch) -> None:
    monkeypatch.setenv("CHAT_DEFAULT_YEAR", "2026")

    from app.core.config import get_settings
    get_settings.cache_clear()
    from app.services import date_context as dc_module
    dc_module._context = None  # noqa: SLF001

    parser = ChatParser()
    query = parser._parse_with_rules(ChatAskRequest(message="покажи отзывы за февраль"))  # noqa: SLF001

    assert query.filters.date_from == "2026-02-01"
    assert query.filters.date_to == "2026-02-28"  # 2026 не високосный


def test_chat_rules_semantic_scope_reads_from_settings(monkeypatch) -> None:
    monkeypatch.setenv("CHAT_SEMANTIC_SCOPE_KEYWORDS", "телевизор,пульт")

    from app.core.config import get_settings
    get_settings.cache_clear()
    from app.services import date_context as dc_module
    dc_module._context = None  # noqa: SLF001

    parser = ChatParser()
    query = parser._parse_with_rules(ChatAskRequest(message="что пишут про пульт"))  # noqa: SLF001

    assert "qdrant" in query.tools
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd service && pytest tests/test_contracts.py tests/test_ru_months.py tests/test_date_context.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Document new env vars**

Append to `service/backend/.env.docker.example`:

```
# Пусто = резолвится из БД (макс. review_date) или today().year как fallback.
CHAT_DEFAULT_YEAR=""
# Comma-separated ключевые слова для детекции semantic scope в чате.
CHAT_SEMANTIC_SCOPE_KEYWORDS="книг,облож,страниц,учебник,роман"
```

Add the same to `service/backend/.env.example`.

- [ ] **Step 6: Verify no hardcoded 2025 or old month tuple remain**

```bash
cd service && grep -n "2025-09\|2025-10\|2025-11\|_MONTH_RANGES\|_SEMANTIC_SCOPE_KEYWORDS" backend/app/services/chat_parser.py
```

Expected: no output.

- [ ] **Step 7: Commit**

```bash
git add service/backend/app/services/chat_parser.py service/tests/test_contracts.py service/backend/.env.docker.example service/backend/.env.example
git commit -m "refactor(chat-parser): drop 2025-only months and books-only scope; drive from settings + DB"
```
