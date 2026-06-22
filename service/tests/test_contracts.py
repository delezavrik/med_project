from app.schemas.query import AnswerMode, ReviewFilters, TemplateExecuteRequest
from app.services.template_parser import TemplateParser


def test_template_parser_count_by_problem() -> None:
    parser = TemplateParser()
    query = parser.parse(
        "count_by_problem",
        TemplateExecuteRequest(
            filters=ReviewFilters(labels=["Доставка/получение"], category="Книги"),
            add_analytical_summary=True,
        ),
    )

    assert query.intent == "count_by_problem"
    assert query.filters.labels == ["Доставка/получение"]
    assert query.filters.category == "Книги"
    assert query.answer_mode == AnswerMode.LLM
    assert query.tools == ["postgres"]
