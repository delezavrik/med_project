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


def test_postgres_tool_warns_when_pool_connection_raises(monkeypatch) -> None:
    class _Boom(Exception):
        pass

    pool = MagicMock()
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(side_effect=_Boom("simulated pool timeout"))
    ctx.__exit__ = MagicMock(return_value=False)
    pool.connection.return_value = ctx

    monkeypatch.setattr(db, "_pool", pool)

    tool = PostgresTool()
    tool.settings = SimpleNamespace(postgres_dsn="postgresql://x", min_total_reviews_for_product_risk=5)

    result = tool.run(_make_query())

    assert any("Ошибка PostgreSQL-инструмента" in w for w in result.warnings)
    # Тул не должен бросать — ошибка pool должна деградировать в warning.
    assert result.rows == []


def test_postgres_tool_coverage_check_uses_pool(monkeypatch) -> None:
    from app.schemas.query import Intent

    main_cursor = MagicMock()
    main_cursor.__enter__.return_value = main_cursor
    main_cursor.fetchall.return_value = []
    main_cursor.fetchone.return_value = {"has_dates": True}

    coverage_cursor = MagicMock()
    coverage_cursor.__enter__.return_value = coverage_cursor
    coverage_cursor.fetchone.return_value = {
        "total": 100,
        "with_product_id": 100,
        "with_product_name": 80,
        "with_category": 60,
        "with_brand": 100,
        "unknown_product_rows": 0,
    }

    call_count = {"n": 0}

    def cursor_factory():
        call_count["n"] += 1
        # First call = main query, later calls (via _add_coverage_info) = coverage query
        return coverage_cursor if call_count["n"] > 1 else main_cursor

    conn = MagicMock()
    conn.__enter__.return_value = conn
    conn.cursor.side_effect = cursor_factory

    pool = MagicMock()
    ctx = MagicMock()
    ctx.__enter__.return_value = conn
    ctx.__exit__.return_value = False
    pool.connection.return_value = ctx

    monkeypatch.setattr(db, "_pool", pool)

    tool = PostgresTool()
    tool.settings = SimpleNamespace(postgres_dsn="postgresql://x", min_total_reviews_for_product_risk=5)

    query = ParsedQuery(
        source=QuerySource.CHAT,
        intent=Intent.TOP_PRODUCTS_BY_PROBLEM,
        filters=ReviewFilters(category="Книги"),
        semantic_query=None,
        tools=[ToolName.POSTGRES],
    )

    result = tool.run(query)

    # _add_coverage_info triggers a second pool.connection() call.
    assert pool.connection.call_count >= 2
    # Coverage gap for "названия товаров" (80/100) должно попасть в warnings.
    assert any("названия товаров" in w for w in result.warnings)
