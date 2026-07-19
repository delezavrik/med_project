"""LLM-парсер свободного вопроса → ParsedQuery.

Использует OpenAI для надёжного распознавания намерения и фильтров с
каноническими метками. При отсутствии ключа/ошибке — откат на rule-based ChatParser.
"""

from __future__ import annotations

import json

from openai import OpenAI

from app.core.config import get_settings
from app.domain.labels import KNOWN_LABELS
from app.schemas.query import (
    AnswerMode, ChatAskRequest, GroupBy, Intent, ParsedQuery, QuerySource, ReviewFilters, ToolName,
)
from app.services.chat_parser import ChatParser

_INTENTS = [i.value for i in Intent]
_EXAMPLE_INTENTS = {"review_examples", "product_summary", "problem_growth_analysis", "recommendations"}

_INSTRUCTIONS = f"""Ты парсер аналитических вопросов о отзывах маркетплейса Wildberries.
По вопросу продавца верни СТРОГО один JSON-объект (без пояснений, без markdown) с полями:
- "intent": одно из {_INTENTS}
- "labels": массив из канонических меток проблем, релевантных вопросу (может быть пустым). Допустимые метки ровно такие: {KNOWN_LABELS}
- "category", "brand", "product_name": строки или null
- "keyword": ключевое слово для текстового поиска или null
- "group_by": "day" | "week" | "month" | null
- "semantic_query": перефразированный смысловой запрос для поиска похожих отзывов или null
- "answer_mode": "llm" если нужен аналитический разбор/объяснение/причины/рекомендации, иначе "template"

Правила сопоставления меток по смыслу:
- размер/маломерит/большемерит/посадка → "Проблема с размером / посадкой"
- брак/дефект/качество/сломан/порвался → "Проблема с качеством товара"
- упаковка/комплект/недокомплект/коробка/пакет → "Проблема с комплектацией / упаковкой"
- не как в описании/не соответствует карточке/фото → "Несоответствие карточке товара"
- цена/дорого/не стоит → "Цена / ценность"
- возврат → "Проблема с возвратом"
- доставка/получение/пункт выдачи → "Проблема доставки / получения"
- позитив/хвалят/нравится → "Положительный / нейтральный отзыв"

Выбор intent:
- "топ проблем"/"главные проблемы" → top_problems
- "сколько"/"количество" по конкретной проблеме → count_by_problem
- "динамика"/"как менялось" → problem_dynamics (укажи group_by)
- "что выросло"/"почему выросли"/"рост" → problem_growth_analysis (answer_mode=llm)
- "покажи отзывы"/"примеры" → review_examples
- "похожие отзывы" по смыслу → review_examples + заполни semantic_query
- про конкретный товар → product_summary (answer_mode=llm)
- "что делать"/"рекомендации" → recommendations (answer_mode=llm)
"""


class LLMChatParser:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.fallback = ChatParser()

    def parse(self, request: ChatAskRequest) -> ParsedQuery:
        if not self.settings.openai_api_key:
            return self.fallback.parse(request)
        try:
            data = self._llm_parse(request.message)
            return self._to_query(data, request)
        except Exception:  # noqa: BLE001
            return self.fallback.parse(request)

    def _llm_parse(self, message: str) -> dict:
        client = OpenAI(api_key=self.settings.openai_api_key)
        resp = client.responses.create(
            model=self.settings.openai_model,
            input=f"{_INSTRUCTIONS}\n\nВопрос: {message}\n\nJSON:",
        )
        text = (resp.output_text or "").strip()
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("no json in llm output")
        return json.loads(text[start : end + 1])

    def _to_query(self, data: dict, request: ChatAskRequest) -> ParsedQuery:
        intent_val = data.get("intent")
        intent = Intent(intent_val) if intent_val in _INTENTS else Intent.TOP_PROBLEMS

        labels = [label for label in (data.get("labels") or []) if label in KNOWN_LABELS]
        group_by_val = data.get("group_by")
        group_by = GroupBy(group_by_val) if group_by_val in {"day", "week", "month"} else None

        filters = ReviewFilters(
            labels=labels,
            category=data.get("category") or None,
            brand=data.get("brand") or None,
            product_name=data.get("product_name") or None,
        )

        answer_mode = AnswerMode.LLM if data.get("answer_mode") == "llm" else AnswerMode.TEMPLATE
        if request.force_answer_mode:
            answer_mode = AnswerMode(request.force_answer_mode)

        limit = 6 if intent.value in _EXAMPLE_INTENTS else 20

        return ParsedQuery(
            source=QuerySource.CHAT,
            intent=intent,
            filters=filters,
            group_by=group_by,
            semantic_query=data.get("semantic_query") or None,
            tools=[ToolName.POSTGRES],
            answer_mode=answer_mode,
            limit=limit,
        )
