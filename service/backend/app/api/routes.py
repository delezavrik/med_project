from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.core.db import get_pool
from app.schemas.query import AnswerResponse, ChatAskRequest, ParsedQuery, TemplateExecuteRequest
from app.services.query_service import QueryService
from app.services.template_registry import list_templates

router = APIRouter()
service = QueryService()


@router.get("/templates")
def get_templates() -> list[dict]:
    return list_templates()


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
