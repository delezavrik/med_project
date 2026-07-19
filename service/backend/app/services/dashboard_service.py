"""Агрегирующий сервис под главный экран (дашборд).

Один запрос → обзор целиком: KPI, топ проблем + рост, динамика, товары, warnings.
Считает СТРОГО по 9 каноническим меткам (app/domain/labels.py) — в review_labels
есть мусорные значения, их отсекаем через `label = ANY(known)`.
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from typing import Any

from app.core.config import get_settings
from app.core.db import get_pool
from app.domain.labels import KNOWN_LABELS, POSITIVE_LABEL, PROBLEM_LABELS
from app.schemas.query import DashboardRequest, ReviewFilters

KEY_BY_LABEL: dict[str, str] = {
    POSITIVE_LABEL: "pos",
    "Проблема с размером / посадкой": "size",
    "Проблема с качеством товара": "quality",
    "Проблема с комплектацией / упаковкой": "pack",
    "Несоответствие карточке товара": "card",
    "Цена / ценность": "price",
    "Проблема с возвратом": "return",
    "Проблема доставки / получения": "delivery",
    "Другая проблема": "other",
}
SHORT_BY_LABEL: dict[str, str] = {
    POSITIVE_LABEL: "Позитив / нейтрал",
    "Проблема с размером / посадкой": "Размер / посадка",
    "Проблема с качеством товара": "Качество (брак / дефект)",
    "Проблема с комплектацией / упаковкой": "Комплектация / упаковка",
    "Несоответствие карточке товара": "Несоответствие карточке",
    "Цена / ценность": "Цена / ценность",
    "Проблема с возвратом": "Возврат",
    "Проблема доставки / получения": "Доставка / получение",
    "Другая проблема": "Другое",
}
GRAN_UNIT = {"day": "дн.", "week": "нед.", "month": "мес."}


def build_dashboard(req: DashboardRequest) -> dict[str, Any]:
    t0 = time.perf_counter()
    settings = get_settings()
    resp = _empty_response(req)
    pool = get_pool()

    if pool is None or not settings.postgres_dsn:
        resp["warnings"].append({"code": "no_db", "message": "База данных недоступна — обзор построить не удалось."})
        return resp

    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                _fill(cur, req, resp)
    except Exception as exc:  # noqa: BLE001
        resp["warnings"].append({"code": "error", "message": f"Не удалось посчитать обзор: {exc}"})

    resp["meta"]["execution_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return resp


# ---------------------------------------------------------------- helpers
def _empty_response(req: DashboardRequest) -> dict[str, Any]:
    return {
        "meta": {
            "total_reviews": 0,
            "granularity": req.granularity,
            "buckets": [],
            "period": {"date_from": None, "date_to": None},
            "prev_period": {"date_from": None, "date_to": None},
            "execution_ms": 0,
        },
        "metrics": [],
        "positive": {"label": POSITIVE_LABEL, "short": SHORT_BY_LABEL[POSITIVE_LABEL], "count": 0, "share": 0.0},
        "problems": [],
        "series": {"negative_share": [], "by_label": {}},
        "positive_vs_problem": {"positive_share": [], "problem_share": []},
        "top_products": [],
        "warnings": [],
        "trace_steps": [],
    }


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _filter_sql(f: ReviewFilters) -> tuple[list[str], dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, Any] = {}
    if f.category:
        clauses.append("r.category = %(category)s")
        params["category"] = f.category
    if f.brand:
        clauses.append("r.brand = %(brand)s")
        params["brand"] = f.brand
    if f.product_id:
        clauses.append("r.product_id = %(product_id)s")
        params["product_id"] = f.product_id
    if f.product_name:
        clauses.append("r.product_name ILIKE %(product_name)s")
        params["product_name"] = f"%{f.product_name}%"
    if f.min_rating is not None:
        clauses.append("r.rating >= %(min_rating)s")
        params["min_rating"] = f.min_rating
    if f.max_rating is not None:
        clauses.append("r.rating <= %(max_rating)s")
        params["max_rating"] = f.max_rating
    return clauses, params


def _scalar(cur, sql: str, params: dict[str, Any]) -> int:
    cur.execute(sql, params)
    row = cur.fetchone() or {}
    val = row.get("c") if isinstance(row, dict) else (row[0] if row else 0)
    return int(val or 0)


def _delta(share: float, prev_share: float, cnt: int) -> tuple[int | None, str]:
    if prev_share > 0:
        d = round((share - prev_share) / prev_share * 100)
        return d, ("up_bad" if d > 0 else "down_good" if d < 0 else "flat")
    return (None, "new" if cnt > 0 else "flat")


# ---------------------------------------------------------------- core
def _fill(cur, req: DashboardRequest, resp: dict[str, Any]) -> None:
    f = req.filters
    gran = req.granularity if req.granularity in GRAN_UNIT else "week"
    base_clauses, base_params = _filter_sql(f)

    # 1) диапазон дат.
    #    robust_mx = 99.5-й перцентиль даты — отсекает редкие «хвостовые» отзывы,
    #    которые иначе растягивают диапазон и оставляют прошлый период пустым.
    cur.execute(
        "SELECT MIN(review_date)::date AS mn, MAX(review_date)::date AS mx, "
        "percentile_disc(0.995) WITHIN GROUP (ORDER BY review_date)::date AS robust_mx "
        "FROM reviews r WHERE "
        + " AND ".join(["r.review_date IS NOT NULL", *base_clauses]),
        base_params,
    )
    row = cur.fetchone() or {}
    mn, mx = row.get("mn"), row.get("mx")
    robust_mx = row.get("robust_mx") or mx
    if mn is None or mx is None:
        resp["warnings"].append({"code": "empty", "message": "По выбранным фильтрам отзывов не нашлось. Попробуйте расширить период или убрать фильтр."})
        return

    user_from, user_to = _parse_date(f.date_from), _parse_date(f.date_to)
    if user_from and user_to:
        # период задан пользователем — уважаем его (в пределах доступных дат)
        df = max(user_from, mn)
        dt = min(user_to, mx)
    else:
        # дефолт: последние ~6 недель плотных данных (чтобы прошлый период тоже был с данными)
        dt = robust_mx
        df = max(mn, dt - timedelta(days=41))
    if df > dt:
        df, dt = mn, robust_mx
    period_days = (dt - df).days + 1
    prev_dt = df - timedelta(days=1)
    prev_df = prev_dt - timedelta(days=period_days - 1)

    where = "r.review_date >= %(df)s AND r.review_date <= %(dt)s" + ("".join(f" AND {c}" for c in base_clauses))
    p_cur = {**base_params, "df": df, "dt": dt}
    p_prev = {**base_params, "df": prev_df, "dt": prev_dt}
    resp["meta"]["period"] = {"date_from": df.isoformat(), "date_to": dt.isoformat()}
    resp["meta"]["prev_period"] = {"date_from": prev_df.isoformat(), "date_to": prev_dt.isoformat()}

    # 2) итоги и метки (текущий + предыдущий период)
    total_cur = _scalar(cur, f"SELECT COUNT(*) AS c FROM reviews r WHERE {where}", p_cur)
    total_prev = _scalar(cur, f"SELECT COUNT(*) AS c FROM reviews r WHERE {where}", p_prev)
    resp["meta"]["total_reviews"] = total_cur
    if total_cur == 0:
        resp["warnings"].append({"code": "empty", "message": "По выбранным фильтрам отзывов не нашлось. Попробуйте расширить период или убрать фильтр."})
        return

    def label_counts(params: dict[str, Any]) -> dict[str, int]:
        cur.execute(
            f"""
            SELECT rl.label, COUNT(DISTINCT r.review_id) AS c
            FROM reviews r JOIN review_labels rl ON rl.review_id = r.review_id
            WHERE {where} AND rl.label = ANY(%(known)s)
            GROUP BY rl.label
            """,
            {**params, "known": KNOWN_LABELS},
        )
        return {r["label"]: int(r["c"]) for r in cur.fetchall()}

    def neg_count(params: dict[str, Any]) -> int:
        return _scalar(
            cur,
            f"""
            SELECT COUNT(DISTINCT r.review_id) AS c
            FROM reviews r JOIN review_labels rl ON rl.review_id = r.review_id
            WHERE {where} AND rl.label = ANY(%(problem)s)
            """,
            {**params, "problem": PROBLEM_LABELS},
        )

    lc_cur, lc_prev = label_counts(p_cur), label_counts(p_prev)
    neg_cur, neg_prev = neg_count(p_cur), neg_count(p_prev)

    # 3) динамика по бакетам
    cur.execute(
        f"SELECT date_trunc(%(gran)s, r.review_date)::date AS bucket, COUNT(*) AS c FROM reviews r WHERE {where} GROUP BY bucket ORDER BY bucket",
        {**p_cur, "gran": gran},
    )
    bucket_rows = cur.fetchall()
    buckets = [r["bucket"] for r in bucket_rows]
    total_by_bucket = {r["bucket"]: int(r["c"]) for r in bucket_rows}

    cur.execute(
        f"""
        SELECT date_trunc(%(gran)s, r.review_date)::date AS bucket, rl.label, COUNT(DISTINCT r.review_id) AS c
        FROM reviews r JOIN review_labels rl ON rl.review_id = r.review_id
        WHERE {where} AND rl.label = ANY(%(known)s)
        GROUP BY bucket, rl.label
        """,
        {**p_cur, "gran": gran, "known": KNOWN_LABELS},
    )
    lab_bucket: dict[tuple[date, str], int] = {(r["bucket"], r["label"]): int(r["c"]) for r in cur.fetchall()}

    cur.execute(
        f"""
        SELECT date_trunc(%(gran)s, r.review_date)::date AS bucket, COUNT(DISTINCT r.review_id) AS c
        FROM reviews r JOIN review_labels rl ON rl.review_id = r.review_id
        WHERE {where} AND rl.label = ANY(%(problem)s)
        GROUP BY bucket
        """,
        {**p_cur, "gran": gran, "problem": PROBLEM_LABELS},
    )
    neg_bucket = {r["bucket"]: int(r["c"]) for r in cur.fetchall()}

    def share_at(b: date, label: str) -> float:
        tot = total_by_bucket.get(b, 0)
        return round(lab_bucket.get((b, label), 0) / tot * 100, 2) if tot else 0.0

    by_label = {KEY_BY_LABEL[label]: [share_at(b, label) for b in buckets] for label in KNOWN_LABELS}
    neg_series = [round(neg_bucket.get(b, 0) / total_by_bucket[b] * 100, 1) if total_by_bucket.get(b) else 0.0 for b in buckets]
    pos_series = by_label["pos"]

    bucket_fmt = "%m.%y" if gran == "month" else "%d.%m"
    resp["meta"]["buckets"] = [b.strftime(bucket_fmt) for b in buckets]
    resp["series"] = {"negative_share": neg_series, "by_label": by_label}
    resp["positive_vs_problem"] = {"positive_share": pos_series, "problem_share": [round(100 - x, 1) for x in pos_series]}

    # 4) позитив + список проблем (с ростом и спарклайном)
    pos_cnt = lc_cur.get(POSITIVE_LABEL, 0)
    resp["positive"] = {
        "label": POSITIVE_LABEL, "short": SHORT_BY_LABEL[POSITIVE_LABEL],
        "count": pos_cnt, "share": round(pos_cnt / total_cur, 4),
    }
    problems: list[dict[str, Any]] = []
    for label in PROBLEM_LABELS:
        key = KEY_BY_LABEL[label]
        cnt = lc_cur.get(label, 0)
        share = cnt / total_cur if total_cur else 0.0
        prev_share = (lc_prev.get(label, 0) / total_prev) if total_prev else 0.0
        delta, ddir = _delta(share, prev_share, cnt)
        problems.append({
            "label_key": key, "label": label, "short": SHORT_BY_LABEL[label],
            "count": cnt, "share": round(share, 4),
            "delta_pct": delta, "delta_dir": ddir,
            "spark": by_label.get(key, []),
        })
    problems.sort(key=lambda p: p["share"], reverse=True)
    resp["problems"] = problems

    # 5) KPI
    neg_share = neg_cur / total_cur * 100 if total_cur else 0.0
    neg_share_prev = neg_prev / total_prev * 100 if total_prev else 0.0
    neg_delta, _ = _delta(neg_share, neg_share_prev, neg_cur)
    # для KPI-заголовка берём существенные проблемы (доля ≥ 3%), чтобы мелкие
    # шумные всплески (напр. доставка 0.8% +168%) не выходили в заголовок.
    growing = [p for p in problems if p["delta_pct"] is not None and p["delta_pct"] > 0]
    material = [p for p in growing if p["share"] >= 0.03]
    top_grow = max(material or growing, key=lambda p: p["delta_pct"], default=None)
    resp["metrics"] = [
        {"name": "Всего отзывов", "value": total_cur, "unit": None, "delta_pct": None, "kind": "fact"},
        {"name": "Доля негатива", "value": round(neg_share, 1), "unit": "%", "delta_pct": neg_delta,
         "delta_dir": "up_bad" if (neg_delta or 0) > 0 else "down_good", "kind": "fact"},
        {"name": "Самая растущая проблема", "value": top_grow["short"] if top_grow else "—", "unit": None,
         "delta_pct": top_grow["delta_pct"] if top_grow else None,
         "label_key": top_grow["label_key"] if top_grow else None, "kind": "fact"},
        {"name": "Период данных", "value": len(buckets), "unit": GRAN_UNIT[gran], "kind": "fact"},
    ]

    # 6) топ товаров по риску
    cur.execute(
        f"""
        SELECT r.product_id,
               MAX(r.product_name) AS product_name,
               MAX(r.brand) AS brand,
               COUNT(DISTINCT r.review_id) AS total,
               COUNT(DISTINCT r.review_id) FILTER (WHERE rl.label = ANY(%(problem)s)) AS problem_cnt
        FROM reviews r LEFT JOIN review_labels rl ON rl.review_id = r.review_id
        WHERE {where} AND COALESCE(r.product_id, '') NOT IN ('', '0')
        GROUP BY r.product_id
        HAVING COUNT(DISTINCT r.review_id) >= 20
        ORDER BY (COUNT(DISTINCT r.review_id) FILTER (WHERE rl.label = ANY(%(problem)s)))::float
                 / NULLIF(COUNT(DISTINCT r.review_id), 0) DESC, total DESC
        LIMIT %(limit)s
        """,
        {**p_cur, "problem": PROBLEM_LABELS, "limit": req.top_products_limit},
    )
    prod_rows = cur.fetchall()
    pids = [r["product_id"] for r in prod_rows]
    top_labels_by_pid: dict[str, list[str]] = {}
    if pids:
        cur.execute(
            f"""
            SELECT product_id, label FROM (
                SELECT r.product_id, rl.label,
                       ROW_NUMBER() OVER (PARTITION BY r.product_id ORDER BY COUNT(DISTINCT r.review_id) DESC) AS rn
                FROM reviews r JOIN review_labels rl ON rl.review_id = r.review_id
                WHERE {where} AND r.product_id = ANY(%(pids)s) AND rl.label = ANY(%(problem)s)
                GROUP BY r.product_id, rl.label
            ) t WHERE rn <= 2 ORDER BY product_id, rn
            """,
            {**p_cur, "pids": pids, "problem": PROBLEM_LABELS},
        )
        for r in cur.fetchall():
            top_labels_by_pid.setdefault(r["product_id"], []).append(KEY_BY_LABEL.get(r["label"], "other"))

    for r in prod_rows:
        total_p = int(r["total"] or 0)
        prob = int(r["problem_cnt"] or 0)
        pshare = prob / total_p if total_p else 0.0
        resp["top_products"].append({
            "product_id": r["product_id"],
            "product_name": r["product_name"] or f"Товар {r['product_id']}",
            "brand": r["brand"] or "",
            "total": total_p,
            "problem_share": round(pshare, 3),
            "risk_score": round(pshare * 100),
            "top_labels": top_labels_by_pid.get(r["product_id"], [])[:2],
        })

    # 7) предупреждения о данных (на языке продавца)
    dated = _scalar(cur, "SELECT COUNT(*) AS c FROM reviews r WHERE r.review_date IS NOT NULL", {})
    all_reviews = _scalar(cur, "SELECT COUNT(*) AS c FROM reviews r", {})
    if all_reviews and dated < all_reviews:
        miss = round((all_reviews - dated) / all_reviews * 100)
        if miss >= 1:
            resp["warnings"].append({"code": "approx_dates", "message": f"У ~{miss}% отзывов нет даты — они не попали в динамику по неделям."})
    if not resp["top_products"]:
        resp["warnings"].append({"code": "sparse_products", "message": "Товар заполнен не у всех отзывов, поэтому рейтинг товаров может быть неполным."})

    # 8) как посчитано
    resp["trace_steps"] = [
        {"id": "filter", "title": "Отобрали отзывы по фильтрам", "status": "ok",
         "input": resp["meta"]["period"], "output": {"reviews": total_cur}},
        {"id": "labels", "title": "Взяли метки классификатора", "status": "ok",
         "input": {}, "output": {"model": "bge-m3 + LinearSVC", "classes": len(KNOWN_LABELS)}},
        {"id": "aggregate", "title": "Свернули в доли и динамику", "status": "ok",
         "input": {"group_by": gran}, "output": {"buckets": len(buckets)}},
        {"id": "delta", "title": "Сравнили с прошлым периодом", "status": "ok",
         "input": resp["meta"]["prev_period"], "output": {"reviews": total_prev}},
    ]
