from app.schemas.query import AnswerMode, AnswerResponse, ParsedQuery, StructuredResult
from app.tools.llm_tool import LLMTool


class AnswerRouter:
    def __init__(self) -> None:
        self.llm = LLMTool()

    def build(self, query: ParsedQuery, result: StructuredResult) -> AnswerResponse:
        if query.answer_mode == AnswerMode.LLM:
            answer_text = self.llm.build_analytical_answer(result)
        else:
            answer_text = self._build_template_answer(result)

        return AnswerResponse(
            parsed_query=query,
            result=result,
            answer_mode=query.answer_mode,
            answer_text=answer_text,
            ui_blocks=self._build_ui_blocks(result),
        )

    def _build_template_answer(self, result: StructuredResult) -> str:
        if result.warnings and not result.rows and not result.metrics and not result.examples:
            return "Не удалось получить данные: " + "; ".join(result.warnings)

        if result.metrics:
            metric = result.metrics[0]
            return f"{metric.name}: {metric.value}"

        if result.rows:
            return f"Найдено строк: {len(result.rows)}"

        if result.examples:
            return f"Найдено примеров отзывов: {len(result.examples)}"

        return "По выбранным фильтрам ничего не найдено."

    def _build_ui_blocks(self, result: StructuredResult) -> list[dict]:
        blocks: list[dict] = []
        if result.metrics:
            blocks.append({"type": "metrics", "items": [m.model_dump() for m in result.metrics]})
        if result.rows:
            blocks.append({"type": "table", "rows": [r.data for r in result.rows]})
        if result.examples:
            blocks.append({"type": "reviews", "items": [e.model_dump() for e in result.examples]})
        if result.warnings:
            blocks.append({"type": "warnings", "items": result.warnings})
        return blocks
