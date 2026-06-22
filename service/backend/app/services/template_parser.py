from app.schemas.query import AnswerMode, ParsedQuery, QuerySource, TemplateExecuteRequest
from app.services.template_registry import get_template


class TemplateParser:
    """Преобразует параметры формы сайта в единый ParsedQuery."""

    def parse(self, template_id: str, request: TemplateExecuteRequest) -> ParsedQuery:
        template = get_template(template_id)

        answer_mode = template.default_answer_mode
        if request.add_analytical_summary and template.allow_llm_summary:
            answer_mode = AnswerMode.LLM

        return ParsedQuery(
            source=QuerySource.TEMPLATE_UI,
            intent=template.intent,
            filters=request.filters,
            group_by=request.group_by or template.default_group_by,
            semantic_query=request.semantic_query,
            tools=template.default_tools,
            answer_mode=answer_mode,
            limit=request.limit,
        )
