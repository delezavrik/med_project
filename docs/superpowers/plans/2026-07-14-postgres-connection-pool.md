# Postgres Connection Pool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace per-request `psycopg.connect(...)` calls in the FastAPI request path with a shared `psycopg_pool.ConnectionPool`, opened on app startup and closed on shutdown.

**Architecture:** Add a `psycopg_pool.ConnectionPool` created inside a FastAPI `lifespan` context manager in `app/main.py`, exposed via a `get_pool()` accessor from a new `app/core/db.py`. Refactor the 5 request-path `psycopg.connect(...)` sites in `app/tools/postgres_tool.py` and `app/api/routes.py` to use `pool.connection()`. Offline scripts in `app/offline/` keep their standalone `psycopg.connect(...)` — they are one-shot processes and don't benefit from a pool.

**Tech Stack:** Python 3.11, FastAPI 0.115, `psycopg[binary]==3.2.3` → upgrade requirement to `psycopg[binary,pool]==3.2.3` (adds `psycopg_pool`), pydantic-settings 2.7.

## Global Constraints

- All SQL parameterisation stays via psycopg named params (`%(name)s`) — never f-string-interpolate user input. Only whitelisted date granularity may be f-stringed. (From CLAUDE.md conventions.)
- Comments and user-facing strings in Russian; identifiers in English.
- Do not touch offline scripts (`app/offline/*`) — they are batch processes with their own connection lifecycle.
- Do not change `psycopg2-binary` usage in `app/offline/repair_labels_from_csv.py` (legacy, out of scope).
- Preserve current error surfacing: `PostgresTool` catches exceptions and appends to `result.warnings` (never raises); routes wrap errors in `HTTPException(500)`. The pool must not change these contracts.

---

### Task 1: Add pool dependency and settings fields

**Files:**
- Modify: `service/backend/requirements.txt`
- Modify: `service/backend/app/core/config.py`
- Modify: `service/backend/.env.docker.example`
- Modify: `service/backend/.env.example`

**Interfaces:**
- Consumes: nothing (starting point).
- Produces: three new `Settings` fields — `postgres_pool_min_size: int = 2`, `postgres_pool_max_size: int = 10`, `postgres_pool_timeout: float = 30.0`. Env-var names: `POSTGRES_POOL_MIN_SIZE`, `POSTGRES_POOL_MAX_SIZE`, `POSTGRES_POOL_TIMEOUT`.

- [ ] **Step 1: Update requirements.txt to pull in psycopg_pool**

Change line 5 of `service/backend/requirements.txt` from:

```
psycopg[binary]==3.2.3
```

to:

```
psycopg[binary,pool]==3.2.3
```

- [ ] **Step 2: Add pool settings to Settings class**

Insert after line 10 (`postgres_dsn: str | None = None`) in `service/backend/app/core/config.py`:

```python
    postgres_pool_min_size: int = 2
    postgres_pool_max_size: int = 10
    postgres_pool_timeout: float = 30.0
```

- [ ] **Step 3: Document env vars in both example files**

Append these lines to `service/backend/.env.docker.example` after line 7 (`POSTGRES_DSN=...`):

```
POSTGRES_POOL_MIN_SIZE="2"
POSTGRES_POOL_MAX_SIZE="10"
POSTGRES_POOL_TIMEOUT="30"
```

Add the same three lines to `service/backend/.env.example` (matching whatever line contains `POSTGRES_DSN`).

- [ ] **Step 4: Rebuild Docker image and verify psycopg_pool importable**

```bash
cd service && docker compose -f docker-compose.dev.yml build backend
docker compose -f docker-compose.dev.yml run --rm backend python -c "import psycopg_pool; print(psycopg_pool.__version__)"
```

Expected: prints a version string (should be `3.2.x`, bundled with psycopg 3.2.3).

- [ ] **Step 5: Commit**

```bash
git add service/backend/requirements.txt service/backend/app/core/config.py service/backend/.env.docker.example service/backend/.env.example
git commit -m "chore: add psycopg_pool dependency and pool size settings"
```

---

### Task 2: Create pool module with test

**Files:**
- Create: `service/backend/app/core/db.py`
- Create: `service/tests/test_pool.py`

**Interfaces:**
- Consumes: `Settings` fields from Task 1 (`postgres_pool_min_size`, `postgres_pool_max_size`, `postgres_pool_timeout`, `postgres_dsn`).
- Produces:
  - `create_pool(settings: Settings) -> ConnectionPool | None` — returns `None` when DSN missing, otherwise an unopened `ConnectionPool` configured with `dict_row` row factory.
  - `set_pool(pool: ConnectionPool | None) -> None` — module-level setter used by lifespan.
  - `get_pool() -> ConnectionPool | None` — module-level getter used by consumers.

- [ ] **Step 1: Write the failing test**

Create `service/tests/test_pool.py`:

```python
from psycopg_pool import ConnectionPool

from app.core.config import Settings
from app.core.db import create_pool, get_pool, set_pool


def test_create_pool_returns_none_when_dsn_missing() -> None:
    settings = Settings(postgres_dsn=None)
    assert create_pool(settings) is None


def test_create_pool_uses_configured_sizes() -> None:
    settings = Settings(
        postgres_dsn="postgresql://user:pass@localhost:5432/db",
        postgres_pool_min_size=3,
        postgres_pool_max_size=7,
        postgres_pool_timeout=12.0,
    )
    pool = create_pool(settings)
    try:
        assert isinstance(pool, ConnectionPool)
        assert pool.min_size == 3
        assert pool.max_size == 7
        assert pool.timeout == 12.0
    finally:
        if pool is not None:
            pool.close()


def test_get_pool_reflects_set_pool() -> None:
    set_pool(None)
    assert get_pool() is None

    settings = Settings(postgres_dsn="postgresql://user:pass@localhost:5432/db")
    pool = create_pool(settings)
    try:
        set_pool(pool)
        assert get_pool() is pool
    finally:
        set_pool(None)
        if pool is not None:
            pool.close()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd service && pytest tests/test_pool.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.core.db'`.

- [ ] **Step 3: Write minimal implementation**

Create `service/backend/app/core/db.py`:

```python
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.core.config import Settings


_pool: ConnectionPool | None = None


def create_pool(settings: Settings) -> ConnectionPool | None:
    """Создаёт (но не открывает) pool. Возвращает None, если DSN не задан."""
    if not settings.postgres_dsn:
        return None
    return ConnectionPool(
        conninfo=settings.postgres_dsn,
        min_size=settings.postgres_pool_min_size,
        max_size=settings.postgres_pool_max_size,
        timeout=settings.postgres_pool_timeout,
        kwargs={"row_factory": dict_row},
        open=False,
    )


def set_pool(pool: ConnectionPool | None) -> None:
    global _pool
    _pool = pool


def get_pool() -> ConnectionPool | None:
    return _pool
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd service && pytest tests/test_pool.py -v
```

Expected: all three tests PASS.

- [ ] **Step 5: Commit**

```bash
git add service/backend/app/core/db.py service/tests/test_pool.py
git commit -m "feat(db): add psycopg connection pool factory and module accessor"
```

---

### Task 3: Wire pool into FastAPI lifespan

**Files:**
- Modify: `service/backend/app/main.py`

**Interfaces:**
- Consumes: `create_pool` / `set_pool` from `app.core.db`.
- Produces: FastAPI app with `lifespan` context manager that opens the pool on startup, closes it on shutdown, and calls `pool.open(wait=True)` so the first request doesn't pay the connection-establishment cost. `settings` still resolved via `get_settings()`.

- [ ] **Step 1: Rewrite main.py**

Replace the contents of `service/backend/app/main.py` with:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.core.db import create_pool, get_pool, set_pool
from app.ui import router as ui_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = create_pool(settings)
    if pool is not None:
        pool.open(wait=True)
    set_pool(pool)
    try:
        yield
    finally:
        current = get_pool()
        set_pool(None)
        if current is not None:
            current.close()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Для MVP. В production указать домен сайта.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}


app.include_router(ui_router)
app.include_router(api_router, prefix=settings.api_prefix)
```

- [ ] **Step 2: Run existing tests to make sure nothing broke**

```bash
cd service && pytest -v
```

Expected: PASS (no test hits the request path yet).

- [ ] **Step 3: Bring up the stack and verify pool opens**

```bash
cd service && docker compose -f docker-compose.dev.yml up -d postgres
docker compose -f docker-compose.dev.yml up backend
```

Watch the backend log for the FastAPI startup banner without exceptions. Then in a second terminal:

```bash
curl -sf http://localhost:8000/health
```

Expected: `{"status":"ok",...}`.

- [ ] **Step 4: Commit**

```bash
git add service/backend/app/main.py
git commit -m "feat(app): open psycopg pool via FastAPI lifespan"
```

---

### Task 4: Refactor PostgresTool to use the pool

**Files:**
- Modify: `service/backend/app/tools/postgres_tool.py`
- Create: `service/tests/test_postgres_tool_pool.py`

**Interfaces:**
- Consumes: `get_pool()` from `app.core.db`.
- Produces: `PostgresTool` no longer imports `psycopg` or `dict_row` at module scope; it acquires connections from `get_pool()`. When `get_pool()` returns `None`, behaviour matches the current `POSTGRES_DSN не задан` warning path.

- [ ] **Step 1: Write the failing test**

Create `service/tests/test_postgres_tool_pool.py`:

```python
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.core import db
from app.schemas.query import Intent, ParsedQuery, QuerySource, ReviewFilters, ToolName
from app.tools.postgres_tool import PostgresTool


def _make_query() -> ParsedQuery:
    return ParsedQuery(
        source=QuerySource.CHAT,
        intent=Intent.COUNT_BY_PROBLEM,
        filters=ReviewFilters(),
        semantic_query=None,
        tools=[ToolName.POSTGRES],
    )


def test_postgres_tool_warns_when_pool_missing(monkeypatch) -> None:
    monkeypatch.setattr(db, "_pool", None)
    tool = PostgresTool()
    tool.settings = SimpleNamespace(postgres_dsn=None)

    result = tool.run(_make_query())

    assert any("POSTGRES_DSN" in w for w in result.warnings)


def test_postgres_tool_uses_pool_connection(monkeypatch) -> None:
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchall.return_value = [{"review_count": 42}]
    cursor.fetchone.return_value = {"has_dates": True}

    conn = MagicMock()
    conn.__enter__.return_value = conn
    conn.cursor.return_value = cursor

    pool = MagicMock()
    pool.connection.return_value = conn
    conn.__enter__.return_value = conn

    monkeypatch.setattr(db, "_pool", pool)

    tool = PostgresTool()
    tool.settings = SimpleNamespace(postgres_dsn="postgresql://x", min_total_reviews_for_product_risk=5)

    result = tool.run(_make_query())

    assert pool.connection.called
    assert any(m.name == "review_count" and m.value == 42 for m in result.metrics)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd service && pytest tests/test_postgres_tool_pool.py -v
```

Expected: FAIL — second test asserts `pool.connection.called` but the tool still calls `psycopg.connect`.

- [ ] **Step 3: Refactor PostgresTool**

Replace `service/backend/app/tools/postgres_tool.py` with:

```python
from typing import Any

from app.core.config import get_settings
from app.core.db import get_pool
from app.schemas.query import Intent, MetricBlock, ParsedQuery, ResultRow, ReviewExample, StructuredResult
from app.services.sql_builder import SQLBuilder


DATE_DEPENDENT_INTENTS = {
    Intent.PROBLEM_DYNAMICS,
    Intent.PERIOD_COMPARISON,
    Intent.PROBLEM_GROWTH,
    Intent.PROBLEM_GROWTH_ANALYSIS,
    Intent.POSITIVE_VS_PROBLEM,
}


class PostgresTool:
    """Инструмент для точных PostgreSQL-агрегатов по отзывам."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.sql_builder = SQLBuilder()

    def run(self, query: ParsedQuery) -> StructuredResult:
        result = StructuredResult(parsed_query=query)

        pool = get_pool()
        if pool is None or not self.settings.postgres_dsn:
            result.warnings.append("POSTGRES_DSN не задан. PostgreSQL-инструмент не был выполнен.")
            return result

        query = self._prepare_query_for_available_dates(query, result, pool)
        if result.warnings and query.intent in DATE_DEPENDENT_INTENTS:
            return result

        sql, params = self.sql_builder.build(query)
        result.parsed_query = query
        result.raw["sql"] = sql
        result.raw["params"] = params

        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    rows: list[dict[str, Any]] = list(cur.fetchall())
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Ошибка PostgreSQL-инструмента: {exc}")
            return result

        result.rows = [ResultRow(data=row) for row in rows]

        if query.intent in {Intent.REVIEW_SAMPLES, Intent.REVIEW_EXAMPLES, Intent.KEYWORD_SEARCH}:
            result.examples = [self._row_to_review_example(row) for row in rows]

        if len(rows) == 1 and "review_count" in rows[0]:
            result.metrics.append(MetricBlock(name="review_count", value=rows[0]["review_count"], unit="reviews"))

        self._add_coverage_info(query, result, pool)
        return result

    def _prepare_query_for_available_dates(self, query: ParsedQuery, result: StructuredResult, pool) -> ParsedQuery:
        uses_date_filter = bool(query.filters.date_from or query.filters.date_to)
        needs_dates = query.intent in DATE_DEPENDENT_INTENTS

        if not uses_date_filter and not needs_dates:
            return query
        if self._has_review_dates(pool):
            return query

        warning = (
            "В PostgreSQL нет заполненного review_date, поэтому аналитика по периодам сейчас недоступна. "
            "Добавь даты в экспорт и перезагрузи базу или запускай сценарии без периода."
        )
        result.warnings.append(warning)

        if needs_dates:
            return query

        prepared = query.model_copy(deep=True)
        prepared.filters.date_from = None
        prepared.filters.date_to = None
        result.parsed_query = prepared
        result.warnings.append("Фильтр периода проигнорирован, чтобы показать результат по всем доступным отзывам.")
        return prepared

    def _has_review_dates(self, pool) -> bool:
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT EXISTS (SELECT 1 FROM reviews WHERE review_date IS NOT NULL) AS has_dates;")
                    row = cur.fetchone()
                    return bool(row and row["has_dates"])
        except Exception:  # noqa: BLE001
            return True

    def _row_to_review_example(self, row: dict[str, Any]) -> ReviewExample:
        labels = row.get("labels") or []
        if isinstance(labels, str):
            labels = [labels]

        return ReviewExample(
            review_id=row.get("review_id"),
            text=row.get("text", ""),
            labels=list(labels),
            product_id=row.get("product_id"),
            product_name=row.get("product_name"),
            category=row.get("category"),
            brand=row.get("brand"),
            rating=row.get("rating"),
            date=row.get("date") or row.get("review_date"),
        )

    def _add_coverage_info(self, query: ParsedQuery, result: StructuredResult, pool) -> None:
        if query.intent != Intent.TOP_PRODUCTS_BY_PROBLEM and not (
            query.filters.product_id
            or query.filters.product_name
            or query.filters.category
            or query.filters.brand
        ):
            return

        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT
                            COUNT(*) AS total,
                            COUNT(product_id) AS with_product_id,
                            COUNT(product_name) AS with_product_name,
                            COUNT(category) AS with_category,
                            COUNT(brand) AS with_brand,
                            COUNT(*) FILTER (WHERE product_id = '0') AS unknown_product_rows
                        FROM reviews;
                        """
                    )
                    coverage = cur.fetchone() or {}
        except Exception:  # noqa: BLE001
            return

        result.raw["data_coverage"] = dict(coverage)
        total = coverage.get("total") or 0
        if not total:
            return

        incomplete_fields = []
        for field, label in (
            ("with_product_name", "названия товаров"),
            ("with_category", "категории"),
            ("with_brand", "бренды"),
        ):
            value = coverage.get(field) or 0
            if value < total:
                incomplete_fields.append(f"{label}: {value}/{total}")

        if incomplete_fields:
            result.warnings.append(
                "Товарное обогащение неполное; результаты по товарам/категориям/брендам могут не покрывать все отзывы. "
                + "; ".join(incomplete_fields)
                + "."
            )

        unknown_product_rows = coverage.get("unknown_product_rows") or 0
        if unknown_product_rows:
            result.warnings.append(
                f"{unknown_product_rows} отзывов имеют product_id=0 и исключаются из товарных топов/фасетов как неизвестный товар."
            )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd service && pytest tests/test_postgres_tool_pool.py tests/test_contracts.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add service/backend/app/tools/postgres_tool.py service/tests/test_postgres_tool_pool.py
git commit -m "refactor(postgres-tool): use shared psycopg pool instead of per-request connect"
```

---

### Task 5: Refactor routes.py to use the pool

**Files:**
- Modify: `service/backend/app/api/routes.py`

**Interfaces:**
- Consumes: `get_pool()` from `app.core.db`.
- Produces: `/facets` and `/debug/db-stats` acquire connections from the pool instead of calling `psycopg.connect`. Behaviour on missing pool matches previous DSN-missing behaviour.

- [ ] **Step 1: Rewrite routes.py**

Replace `service/backend/app/api/routes.py` with:

```python
from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.core.db import get_pool
from app.domain.labels import KNOWN_LABELS, PROBLEM_LABELS, POSITIVE_LABEL
from app.schemas.query import AnswerResponse, ChatAskRequest, ParsedQuery, TemplateExecuteRequest
from app.services.query_service import QueryService
from app.services.template_registry import list_templates

router = APIRouter()
service = QueryService()


@router.get("/templates")
def get_templates() -> list[dict]:
    return list_templates()


@router.get("/facets")
def get_facets() -> dict:
    """Возвращает значения фильтров для UI."""
    settings = get_settings()
    facets = {
        "labels": KNOWN_LABELS,
        "problem_labels": PROBLEM_LABELS,
        "positive_label": POSITIVE_LABEL,
        "categories": [],
        "brands": [],
        "products": [],
        "date_min": None,
        "date_max": None,
        "warnings": [],
    }

    pool = get_pool()
    if pool is None or not settings.postgres_dsn:
        facets["warnings"].append("POSTGRES_DSN не задан. Доступны только встроенные labels.")
        return facets

    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        MIN(review_date)::text AS date_min,
                        MAX(review_date)::text AS date_max
                    FROM reviews;
                    """
                )
                dates = cur.fetchone() or {}
                facets["date_min"] = dates.get("date_min")
                facets["date_max"] = dates.get("date_max")
                if facets["date_min"] is None or facets["date_max"] is None:
                    facets["warnings"].append(
                        "В PostgreSQL нет дат отзывов: фильтр периода отключен, пока в экспорте нет review_date."
                    )

                cur.execute(
                    """
                    SELECT DISTINCT category
                    FROM reviews
                    WHERE category IS NOT NULL AND category <> ''
                    ORDER BY category
                    LIMIT 100;
                    """
                )
                facets["categories"] = [row["category"] for row in cur.fetchall()]

                cur.execute(
                    """
                    SELECT DISTINCT brand
                    FROM reviews
                    WHERE brand IS NOT NULL AND brand <> ''
                    ORDER BY brand
                    LIMIT 100;
                    """
                )
                facets["brands"] = [row["brand"] for row in cur.fetchall()]

                cur.execute(
                    """
                    SELECT DISTINCT product_id, product_name
                    FROM reviews
                    WHERE (product_id IS NOT NULL OR product_name IS NOT NULL)
                        AND COALESCE(product_id, '') NOT IN ('', '0')
                    ORDER BY product_name NULLS LAST, product_id NULLS LAST
                    LIMIT 200;
                    """
                )
                facets["products"] = list(cur.fetchall())
    except Exception as exc:  # noqa: BLE001
        facets["warnings"].append(f"PostgreSQL facets error: {exc}")

    return facets


@router.post("/templates/{template_id}/execute", response_model=AnswerResponse)
def execute_template(template_id: str, request: TemplateExecuteRequest) -> AnswerResponse:
    try:
        return service.execute_template(template_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/query/execute", response_model=AnswerResponse)
def execute_query(query: ParsedQuery) -> AnswerResponse:
    return service.execute_parsed_query(query)


@router.post("/chat/ask", response_model=AnswerResponse)
def ask_chat(request: ChatAskRequest) -> AnswerResponse:
    return service.ask_chat(request)


@router.get("/debug/db-stats")
def db_stats() -> dict:
    """Быстрая проверка, что backend видит PostgreSQL и что данные импортированы."""
    settings = get_settings()
    pool = get_pool()
    if pool is None or not settings.postgres_dsn:
        raise HTTPException(status_code=500, detail="POSTGRES_DSN не задан")

    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS reviews_count FROM reviews;")
                reviews_count = cur.fetchone()["reviews_count"]

                cur.execute("SELECT COUNT(*) AS labels_count FROM review_labels;")
                labels_count = cur.fetchone()["labels_count"]

                cur.execute(
                    """
                    SELECT label, COUNT(*) AS review_count
                    FROM review_labels
                    GROUP BY label
                    ORDER BY review_count DESC
                    LIMIT 20;
                    """
                )
                labels = list(cur.fetchall())
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"PostgreSQL error: {exc}") from exc

    return {
        "reviews_count": reviews_count,
        "labels_count": labels_count,
        "top_labels": labels,
    }
```

- [ ] **Step 2: Grep to confirm no request-path psycopg.connect remains**

```bash
cd service && grep -rn "psycopg.connect" backend/app/api backend/app/tools
```

Expected: no output.

- [ ] **Step 3: Bring the stack up and hit both endpoints**

```bash
cd service && docker compose -f docker-compose.dev.yml up -d
sleep 5
curl -sf http://localhost:8000/api/v1/debug/db-stats
curl -sf http://localhost:8000/api/v1/facets
```

Expected: both return valid JSON (may include `warnings` array; no HTTP error).

- [ ] **Step 4: Commit**

```bash
git add service/backend/app/api/routes.py
git commit -m "refactor(routes): use shared psycopg pool in /facets and /debug/db-stats"
```

---

### Task 6: Smoke test under repeated load

**Files:**
- Modify: `service/scripts/smoke_test.sh` (only if it does not already loop the endpoints — otherwise create an ad-hoc check step and skip file changes).

**Interfaces:**
- Consumes: the running backend from Task 5.
- Produces: evidence that repeated requests reuse pool connections (no `connection refused`, latency stable).

- [ ] **Step 1: Hammer the endpoints and observe**

```bash
for i in $(seq 1 50); do
  curl -sf -o /dev/null -w "%{time_total}\n" http://localhost:8000/api/v1/debug/db-stats
done
```

Expected: 50 lines of latency values, no failures. Requests after the first should be noticeably faster than a cold connect (typically <50 ms).

- [ ] **Step 2: Verify pool metrics on backend log**

Check backend logs — the pool should have opened once at startup and not emitted repeated "connection created" messages. If psycopg_pool logging is off, this is skipped.

```bash
cd service && docker compose -f docker-compose.dev.yml logs backend | grep -i "pool" | head
```

- [ ] **Step 3: Shut down and verify pool closes cleanly**

```bash
cd service && docker compose -f docker-compose.dev.yml stop backend
docker compose -f docker-compose.dev.yml logs backend | tail -20
```

Expected: no unhandled exceptions during shutdown; pool `.close()` runs from lifespan finally block.

- [ ] **Step 4: Commit (only if smoke_test.sh was modified — otherwise skip)**

```bash
git add service/scripts/smoke_test.sh
git commit -m "test: exercise repeated requests to validate psycopg pool reuse"
```
