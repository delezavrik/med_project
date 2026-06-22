from openai import OpenAI
from app.core.config import get_settings
from app.schemas.query import StructuredResult


class LLMTool:
    """Финальный аналитический слой.

    Получает только структурированные данные, а не полный датасет.
    Это снижает риск галлюцинаций: LLM объясняет уже посчитанные факты.
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def build_analytical_answer(self, result: StructuredResult) -> str:
        if not self.settings.openai_api_key:
            return self._fallback_answer(result)

        client = OpenAI(api_key=self.settings.openai_api_key)
        prompt = self._build_prompt(result)

        response = client.responses.create(
            model=self.settings.openai_model,
            input=prompt,
        )
        return response.output_text

    def _build_prompt(self, result: StructuredResult) -> str:
        return f"""
Ты аналитик сервиса отзывов маркетплейса.
Сделай краткий вывод по структурированным данным.

Правила:
- не придумывай причин, которых нет в данных;
- отделяй факт от гипотезы;
- пиши коротко и прикладно для продавца;
- если данных мало, прямо скажи об этом.

ParsedQuery:
{result.parsed_query.model_dump_json(indent=2)}

Metrics:
{[m.model_dump() for m in result.metrics]}

Rows:
{[r.data for r in result.rows[:30]]}

Examples:
{[e.model_dump() for e in result.examples[:10]]}

Warnings:
{result.warnings}
""".strip()

    def _fallback_answer(self, result: StructuredResult) -> str:
        if result.warnings:
            return "Данные получены не полностью: " + "; ".join(result.warnings)
        if result.metrics:
            parts = [f"{m.name}: {m.value}" for m in result.metrics]
            return "Краткий результат: " + ", ".join(parts) + ". Для аналитического вывода подключи OPENAI_API_KEY."
        if result.rows:
            return f"Найдено строк: {len(result.rows)}. Для аналитического вывода подключи OPENAI_API_KEY."
        if result.examples:
            return f"Найдено примеров отзывов: {len(result.examples)}. Для аналитического вывода подключи OPENAI_API_KEY."
        return "Данных для вывода пока нет. Проверь фильтры и подключение инструментов."
