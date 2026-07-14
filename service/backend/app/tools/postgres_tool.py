from typing import Any

from app.core.config import get_settings
from app.core.db import get_pool
from app.schemas.query import Intent, MetricBlock, ParsedQuery, ResultRow, ReviewExample, StructuredResult
from app.services.sql_builder import SQLBuilder


DATE_DEPENDENT_INTENTS = {
    Intent.PROBLEM_DYNAMICS,
    Intent.PERIOD_COMPARISON,
    Intent.PROBLEM_GROWTH_ANALYSIS,
}


class PostgresTool:
    """Инструмент для точных PostgreSQL-агрегатов по отзывам."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.sql_builder = SQLBuilder()

    def run(self, query: ParsedQuery) -> StructuredResult:
        result = StructuredResult(parsed_query=query)

        pool = get_pool()
        if pool is None or not self.settings.postgres_dsn:
            result.warnings.append("POSTGRES_DSN не задан. PostgreSQL-инструмент не был выполнен.")
            return result

        query = self._prepare_query_for_available_dates(query, result, pool)
        if result.warnings and query.intent in DATE_DEPENDENT_INTENTS:
            return result

        sql, params = self.sql_builder.build(query)
        result.parsed_query = query
        result.raw["sql"] = sql
        result.raw["params"] = params

        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    rows: list[dict[str, Any]] = list(cur.fetchall())
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Ошибка PostgreSQL-инструмента: {exc}")
            return result

        result.rows = [ResultRow(data=row) for row in rows]

        if query.intent in {Intent.REVIEW_EXAMPLES}:
            result.examples = [self._row_to_review_example(row) for row in rows]

        if len(rows) == 1 and "review_count" in rows[0]:
            result.metrics.append(MetricBlock(name="review_count", value=rows[0]["review_count"], unit="reviews"))

        self._add_coverage_info(query, result, pool)
        return result

    def _prepare_query_for_available_dates(self, query: ParsedQuery, result: StructuredResult, pool) -> ParsedQuery:
        uses_date_filter = bool(query.filters.date_from or query.filters.date_to)
        needs_dates = query.intent in DATE_DEPENDENT_INTENTS

        if not uses_date_filter and not needs_dates:
            return query
        if self._has_review_dates(pool):
            return query

        warning = (
            "В PostgreSQL нет заполненного review_date, поэтому аналитика по периодам сейчас недоступна. "
            "Добавь даты в экспорт и перезагрузи базу или запускай сценарии без периода."
        )
        result.warnings.append(warning)

        if needs_dates:
            return query

        prepared = query.model_copy(deep=True)
        prepared.filters.date_from = None
        prepared.filters.date_to = None
        result.parsed_query = prepared
        result.warnings.append("Фильтр периода проигнорирован, чтобы показать результат по всем доступным отзывам.")
        return prepared

    def _has_review_dates(self, pool) -> bool:
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT EXISTS (SELECT 1 FROM reviews WHERE review_date IS NOT NULL) AS has_dates;")
                    row = cur.fetchone()
                    return bool(row and row["has_dates"])
        except Exception:  # noqa: BLE001
            return True

    def _row_to_review_example(self, row: dict[str, Any]) -> ReviewExample:
        labels = row.get("labels") or []
        if isinstance(labels, str):
            labels = [labels]

        return ReviewExample(
            review_id=row.get("review_id"),
            text=row.get("text", ""),
            labels=list(labels),
            product_name=row.get("product_name"),
            rating=row.get("rating"),
            date=row.get("date") or row.get("review_date"),
        )

    def _add_coverage_info(self, query: ParsedQuery, result: StructuredResult, pool) -> None:
        if query.intent != Intent.TOP_PRODUCTS_BY_PROBLEM and not (
            query.filters.product_id
            or query.filters.product_name
            or query.filters.category
            or query.filters.brand
        ):
            return

        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT
                            COUNT(*) AS total,
                            COUNT(product_id) AS with_product_id,
                            COUNT(product_name) AS with_product_name,
                            COUNT(category) AS with_category,
                            COUNT(brand) AS with_brand,
                            COUNT(*) FILTER (WHERE product_id = '0') AS unknown_product_rows
                        FROM reviews;
                        """
                    )
                    coverage = cur.fetchone() or {}
        except Exception:  # noqa: BLE001
            return

        result.raw["data_coverage"] = dict(coverage)
        total = coverage.get("total") or 0
        if not total:
            return

        incomplete_fields = []
        for field, label in (
            ("with_product_name", "названия товаров"),
            ("with_category", "категории"),
            ("with_brand", "бренды"),
        ):
            value = coverage.get(field) or 0
            if value < total:
                incomplete_fields.append(f"{label}: {value}/{total}")

        if incomplete_fields:
            result.warnings.append(
                "Товарное обогащение неполное; результаты по товарам/категориям/брендам могут не покрывать все отзывы. "
                + "; ".join(incomplete_fields)
                + "."
            )

        unknown_product_rows = coverage.get("unknown_product_rows") or 0
        if unknown_product_rows:
            result.warnings.append(
                f"{unknown_product_rows} отзывов имеют product_id=0 и исключаются из товарных топов/фасетов как неизвестный товар."
            )
