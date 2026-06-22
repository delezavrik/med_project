from dataclasses import dataclass
from app.schemas.query import AnswerMode, GroupBy, Intent, ToolName


@dataclass(frozen=True)
class TemplateConfig:
    id: str
    title: str
    description: str
    intent: Intent
    default_tools: list[ToolName]
    default_answer_mode: AnswerMode
    allow_llm_summary: bool
    default_group_by: GroupBy | None = None
    needs_semantic_query: bool = False


TEMPLATE_REGISTRY: dict[str, TemplateConfig] = {
    "count_by_problem": TemplateConfig(
        id="count_by_problem",
        title="Количество отзывов по проблеме",
        description="Считает, сколько отзывов попало в выбранный класс проблемы.",
        intent=Intent.COUNT_BY_PROBLEM,
        default_tools=[ToolName.POSTGRES],
        default_answer_mode=AnswerMode.TEMPLATE,
        allow_llm_summary=True,
    ),
    "top_problems": TemplateConfig(
        id="top_problems",
        title="Главные проблемы за период",
        description="Показывает топ классов проблем по количеству отзывов.",
        intent=Intent.TOP_PROBLEMS,
        default_tools=[ToolName.POSTGRES],
        default_answer_mode=AnswerMode.TEMPLATE,
        allow_llm_summary=True,
        default_group_by=GroupBy.LABEL,
    ),
    "problem_dynamics": TemplateConfig(
        id="problem_dynamics",
        title="Динамика проблемы",
        description="Показывает, как менялось количество отзывов по проблеме во времени.",
        intent=Intent.PROBLEM_DYNAMICS,
        default_tools=[ToolName.POSTGRES],
        default_answer_mode=AnswerMode.TEMPLATE,
        allow_llm_summary=True,
        default_group_by=GroupBy.WEEK,
    ),
    "top_products_by_problem": TemplateConfig(
        id="top_products_by_problem",
        title="Топ товаров по проблеме",
        description="Показывает товары, у которых чаще всего встречается выбранная проблема.",
        intent=Intent.TOP_PRODUCTS_BY_PROBLEM,
        default_tools=[ToolName.POSTGRES],
        default_answer_mode=AnswerMode.TEMPLATE,
        allow_llm_summary=True,
        default_group_by=GroupBy.PRODUCT,
    ),
    "review_examples": TemplateConfig(
        id="review_examples",
        title="Примеры отзывов",
        description="Ищет конкретные отзывы и похожие жалобы по смыслу.",
        intent=Intent.REVIEW_EXAMPLES,
        default_tools=[ToolName.QDRANT],
        default_answer_mode=AnswerMode.TEMPLATE,
        allow_llm_summary=False,
        needs_semantic_query=True,
    ),
    "period_comparison": TemplateConfig(
        id="period_comparison",
        title="Сравнение периодов",
        description="Сравнивает проблемы между двумя периодами. В MVP второй период задается на уровне frontend.",
        intent=Intent.PERIOD_COMPARISON,
        default_tools=[ToolName.POSTGRES],
        default_answer_mode=AnswerMode.LLM,
        allow_llm_summary=True,
    ),
    "product_summary": TemplateConfig(
        id="product_summary",
        title="Сводка по товару",
        description="Собирает метрики и примеры отзывов по одному товару.",
        intent=Intent.PRODUCT_SUMMARY,
        default_tools=[ToolName.POSTGRES, ToolName.QDRANT],
        default_answer_mode=AnswerMode.LLM,
        allow_llm_summary=True,
    ),
    "recommendations": TemplateConfig(
        id="recommendations",
        title="Рекомендации продавцу",
        description="Формирует выводы и рекомендации на основе метрик и примеров отзывов.",
        intent=Intent.RECOMMENDATIONS,
        default_tools=[ToolName.POSTGRES, ToolName.QDRANT],
        default_answer_mode=AnswerMode.LLM,
        allow_llm_summary=True,
    ),
}


def list_templates() -> list[dict]:
    return [
        {
            "id": template.id,
            "title": template.title,
            "description": template.description,
            "default_answer_mode": template.default_answer_mode,
            "allow_llm_summary": template.allow_llm_summary,
            "needs_semantic_query": template.needs_semantic_query,
        }
        for template in TEMPLATE_REGISTRY.values()
    ]


def get_template(template_id: str) -> TemplateConfig:
    try:
        return TEMPLATE_REGISTRY[template_id]
    except KeyError as exc:
        raise ValueError(f"Unknown template_id: {template_id}") from exc
