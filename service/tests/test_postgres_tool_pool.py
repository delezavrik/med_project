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
