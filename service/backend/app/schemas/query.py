from enum import StrEnum
from typing import Any, Literal
from pydantic import BaseModel, Field


class QuerySource(StrEnum):
    TEMPLATE_UI = "template_ui"
    CHAT = "chat"


class ToolName(StrEnum):
    POSTGRES = "postgres"
    QDRANT = "qdrant"


class AnswerMode(StrEnum):
    TEMPLATE = "template"
    LLM = "llm"


class Intent(StrEnum):
    COUNT_BY_PROBLEM = "count_by_problem"
    TOP_PROBLEMS = "top_problems"
    PROBLEM_DYNAMICS = "problem_dynamics"
    TOP_PRODUCTS_BY_PROBLEM = "top_products_by_problem"
    REVIEW_EXAMPLES = "review_examples"
    PERIOD_COMPARISON = "period_comparison"
    PRODUCT_SUMMARY = "product_summary"
    RECOMMENDATIONS = "recommendations"
    PROBLEM_GROWTH_ANALYSIS = "problem_growth_analysis"


class GroupBy(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    PRODUCT = "product"
    BRAND = "brand"
    CATEGORY = "category"
    LABEL = "label"


class ReviewFilters(BaseModel):
    date_from: str | None = Field(default=None, description="Дата начала в формате YYYY-MM-DD")
    date_to: str | None = Field(default=None, description="Дата конца в формате YYYY-MM-DD")
    labels: list[str] = Field(default_factory=list)
    category: str | None = None
    brand: str | None = None
    product_id: str | None = None
    product_name: str | None = None
    min_rating: int | None = Field(default=None, ge=1, le=5)
    max_rating: int | None = Field(default=None, ge=1, le=5)


class ParsedQuery(BaseModel):
    source: QuerySource
    intent: Intent
    filters: ReviewFilters = Field(default_factory=ReviewFilters)
    group_by: GroupBy | None = None
    semantic_query: str | None = None
    tools: list[ToolName] = Field(default_factory=list)
    answer_mode: AnswerMode = AnswerMode.TEMPLATE
    limit: int = Field(default=20, ge=1, le=200)


class MetricBlock(BaseModel):
    name: str
    value: int | float | str | None
    unit: str | None = None


class ResultRow(BaseModel):
    data: dict[str, Any]


class ReviewExample(BaseModel):
    review_id: str | None = None
    text: str
    labels: list[str] = Field(default_factory=list)
    product_name: str | None = None
    rating: int | None = None
    date: str | None = None
    score: float | None = None


class StructuredResult(BaseModel):
    parsed_query: ParsedQuery
    metrics: list[MetricBlock] = Field(default_factory=list)
    rows: list[ResultRow] = Field(default_factory=list)
    examples: list[ReviewExample] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class AnswerResponse(BaseModel):
    parsed_query: ParsedQuery
    result: StructuredResult
    answer_mode: AnswerMode
    answer_text: str
    ui_blocks: list[dict[str, Any]] = Field(default_factory=list)
    # Фронт объявляет trace_steps как required — без поля здесь фронт получит undefined
    # и упадёт с TypeError в ResultView (белый экран). AnswerRouter кладёт сюда
    # значение из result.raw["trace_steps"].
    trace_steps: list[dict[str, Any]] = Field(default_factory=list)
    execution_ms: float | None = None


class TemplateExecuteRequest(BaseModel):
    filters: ReviewFilters = Field(default_factory=ReviewFilters)
    group_by: GroupBy | None = None
    semantic_query: str | None = None
    add_analytical_summary: bool = False
    limit: int = Field(default=20, ge=1, le=200)


class ChatAskRequest(BaseModel):
    message: str
    force_answer_mode: Literal["template", "llm"] | None = None


class DashboardRequest(BaseModel):
    filters: ReviewFilters = Field(default_factory=ReviewFilters)
    granularity: Literal["day", "week", "month"] = "week"
    top_products_limit: int = Field(default=5, ge=1, le=20)
