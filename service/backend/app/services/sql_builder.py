from typing import Any
from app.schemas.query import GroupBy, Intent, ParsedQuery


class SQLBuilder:
    """Собирает безопасные SQL-шаблоны под основные intent.

    Здесь не должно быть SQL, склеенного из пользовательских строк.
    Все значения идут через params.
    """

    def build(self, query: ParsedQuery) -> tuple[str, dict[str, Any]]:
        where_sql, params = self._build_filters(query)

        if query.intent == Intent.COUNT_BY_PROBLEM:
            return self._count_by_problem(where_sql, params)
        if query.intent == Intent.TOP_PROBLEMS:
            return self._top_problems(where_sql, params, query.limit)
        if query.intent == Intent.PROBLEM_DYNAMICS:
            return self._problem_dynamics(where_sql, params, query.group_by or GroupBy.WEEK)
        if query.intent == Intent.TOP_PRODUCTS_BY_PROBLEM:
            return self._top_products(where_sql, params, query.limit)

        # Для сложных intent сначала возвращаем базовые агрегаты.
        return self._top_problems(where_sql, params, query.limit)

    def _build_filters(self, query: ParsedQuery) -> tuple[str, dict[str, Any]]:
        filters = query.filters
        clauses = ["1 = 1"]
        params: dict[str, Any] = {}

        if filters.date_from:
            clauses.append("r.review_date >= %(date_from)s")
            params["date_from"] = filters.date_from
        if filters.date_to:
            clauses.append("r.review_date <= %(date_to)s")
            params["date_to"] = filters.date_to
        if filters.category:
            clauses.append("r.category = %(category)s")
            params["category"] = filters.category
        if filters.brand:
            clauses.append("r.brand = %(brand)s")
            params["brand"] = filters.brand
        if filters.product_id:
            clauses.append("r.product_id = %(product_id)s")
            params["product_id"] = filters.product_id
        if filters.product_name:
            clauses.append("r.product_name ILIKE %(product_name)s")
            params["product_name"] = f"%{filters.product_name}%"
        if filters.min_rating is not None:
            clauses.append("r.rating >= %(min_rating)s")
            params["min_rating"] = filters.min_rating
        if filters.max_rating is not None:
            clauses.append("r.rating <= %(max_rating)s")
            params["max_rating"] = filters.max_rating
        if filters.labels:
            clauses.append("rl.label = ANY(%(labels)s)")
            params["labels"] = filters.labels

        return " AND ".join(clauses), params

    def _count_by_problem(self, where_sql: str, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        sql = f"""
        SELECT COUNT(DISTINCT r.review_id) AS review_count
        FROM reviews r
        LEFT JOIN review_labels rl ON rl.review_id = r.review_id
        WHERE {where_sql};
        """
        return sql, params

    def _top_problems(self, where_sql: str, params: dict[str, Any], limit: int) -> tuple[str, dict[str, Any]]:
        params = {**params, "limit": limit}
        sql = f"""
        SELECT rl.label, COUNT(DISTINCT r.review_id) AS review_count
        FROM reviews r
        JOIN review_labels rl ON rl.review_id = r.review_id
        WHERE {where_sql}
        GROUP BY rl.label
        ORDER BY review_count DESC
        LIMIT %(limit)s;
        """
        return sql, params

    def _problem_dynamics(self, where_sql: str, params: dict[str, Any], group_by: GroupBy) -> tuple[str, dict[str, Any]]:
        date_granularity = {
            GroupBy.DAY: "day",
            GroupBy.WEEK: "week",
            GroupBy.MONTH: "month",
        }.get(group_by, "week")

        sql = f"""
        SELECT
            DATE_TRUNC('{date_granularity}', r.review_date)::date AS period,
            COALESCE(rl.label, 'Без класса') AS label,
            COUNT(DISTINCT r.review_id) AS review_count
        FROM reviews r
        LEFT JOIN review_labels rl ON rl.review_id = r.review_id
        WHERE {where_sql}
        GROUP BY period, label
        ORDER BY period ASC, review_count DESC;
        """
        return sql, params

    def _top_products(self, where_sql: str, params: dict[str, Any], limit: int) -> tuple[str, dict[str, Any]]:
        params = {**params, "limit": limit}
        sql = f"""
        SELECT
            r.product_id,
            r.product_name,
            COUNT(DISTINCT r.review_id) AS review_count
        FROM reviews r
        LEFT JOIN review_labels rl ON rl.review_id = r.review_id
        WHERE {where_sql}
        GROUP BY r.product_id, r.product_name
        ORDER BY review_count DESC
        LIMIT %(limit)s;
        """
        return sql, params
