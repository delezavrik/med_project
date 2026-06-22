from typing import Any
import psycopg
from psycopg.rows import dict_row

from app.core.config import get_settings
from app.schemas.query import MetricBlock, ParsedQuery, ResultRow, StructuredResult
from app.services.sql_builder import SQLBuilder


class PostgresTool:
    """Инструмент для точных агрегатов по отзывам."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.sql_builder = SQLBuilder()

    def run(self, query: ParsedQuery) -> StructuredResult:
        result = StructuredResult(parsed_query=query)

        if not self.settings.postgres_dsn:
            result.warnings.append("POSTGRES_DSN не задан. PostgreSQL-инструмент не был выполнен.")
            return result

        sql, params = self.sql_builder.build(query)
        result.raw["sql"] = sql
        result.raw["params"] = params

        try:
            with psycopg.connect(self.settings.postgres_dsn, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    rows: list[dict[str, Any]] = list(cur.fetchall())
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Ошибка PostgreSQL-инструмента: {exc}")
            return result

        result.rows = [ResultRow(data=row) for row in rows]

        if len(rows) == 1 and "review_count" in rows[0]:
            result.metrics.append(MetricBlock(name="review_count", value=rows[0]["review_count"], unit="reviews"))

        return result
