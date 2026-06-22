from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import Json, execute_values
from tqdm.auto import tqdm

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://reviews_user:reviews_password@localhost:5432/reviews_db")
POSTGRES_REVIEWS_PATH = Path(os.getenv(
    "POSTGRES_REVIEWS_PATH",
    "data/db_exports/postgres_reviews_bge_m3_linearsvc_saved_model/reviews_for_postgres.parquet",
))
BATCH_SIZE = int(os.getenv("POSTGRES_LOAD_BATCH_SIZE", "5000"))
TRUNCATE_BEFORE_LOAD = os.getenv("TRUNCATE_BEFORE_LOAD", "0") == "1"

MAIN_COLUMNS = {
    "review_id",
    "review_text",
    "predicted_labels",
    "predicted_labels_str",
    "rating",
    "category",
    "subject",
    "brand",
    "product_id",
    "product_name",
    "seller_id",
    "nm_id",
    "imt_id",
    "supplier_id",
    "feedback_id",
    "review_date",
    "source_dataset",
    "text_column_source",
    "classifier_embedding_model",
    "classifier_model",
}

INSERT_SQL = """
INSERT INTO reviews (
    review_id,
    review_text,
    predicted_labels,
    predicted_labels_str,
    rating,
    category,
    subject,
    brand,
    product_id,
    product_name,
    seller_id,
    nm_id,
    imt_id,
    supplier_id,
    feedback_id,
    review_date,
    source_dataset,
    text_column_source,
    classifier_embedding_model,
    classifier_model,
    raw_metadata
)
VALUES %s
ON CONFLICT (review_id) DO UPDATE SET
    review_text = EXCLUDED.review_text,
    predicted_labels = EXCLUDED.predicted_labels,
    predicted_labels_str = EXCLUDED.predicted_labels_str,
    rating = EXCLUDED.rating,
    category = EXCLUDED.category,
    subject = EXCLUDED.subject,
    brand = EXCLUDED.brand,
    product_id = EXCLUDED.product_id,
    product_name = EXCLUDED.product_name,
    seller_id = EXCLUDED.seller_id,
    nm_id = EXCLUDED.nm_id,
    imt_id = EXCLUDED.imt_id,
    supplier_id = EXCLUDED.supplier_id,
    feedback_id = EXCLUDED.feedback_id,
    review_date = EXCLUDED.review_date,
    source_dataset = EXCLUDED.source_dataset,
    text_column_source = EXCLUDED.text_column_source,
    classifier_embedding_model = EXCLUDED.classifier_embedding_model,
    classifier_model = EXCLUDED.classifier_model,
    raw_metadata = EXCLUDED.raw_metadata;
"""


def clean_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and np.isnan(value):
        return None
    if pd.isna(value) if not isinstance(value, (list, dict, tuple, np.ndarray)) else False:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value):
            return None
        return float(value)
    if isinstance(value, (pd.Timestamp,)):
        if pd.isna(value):
            return None
        return value.isoformat()
    if isinstance(value, np.ndarray):
        return [clean_value(x) for x in value.tolist()]
    return value


def parse_labels(value: Any) -> list[str]:
    value = clean_value(value)
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, tuple):
        return [str(x).strip() for x in value if str(x).strip()]
    s = str(value).strip()
    if not s:
        return []
    try:
        parsed = json.loads(s)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    except Exception:
        pass
    if "|" in s:
        return [x.strip() for x in s.split("|") if x.strip()]
    return [s]


def get_col(row: pd.Series, name: str) -> Any:
    if name not in row.index:
        return None
    return clean_value(row[name])


def row_to_tuple(row: pd.Series) -> tuple[Any, ...]:
    raw_metadata = {}
    for col in row.index:
        if col not in MAIN_COLUMNS:
            value = clean_value(row[col])
            if value is not None:
                raw_metadata[col] = value

    return (
        int(row["review_id"]),
        str(row["review_text"]),
        Json(parse_labels(row.get("predicted_labels"))),
        get_col(row, "predicted_labels_str"),
        get_col(row, "rating"),
        get_col(row, "category"),
        get_col(row, "subject"),
        get_col(row, "brand"),
        str(get_col(row, "product_id")) if get_col(row, "product_id") is not None else None,
        get_col(row, "product_name"),
        str(get_col(row, "seller_id")) if get_col(row, "seller_id") is not None else None,
        str(get_col(row, "nm_id")) if get_col(row, "nm_id") is not None else None,
        str(get_col(row, "imt_id")) if get_col(row, "imt_id") is not None else None,
        str(get_col(row, "supplier_id")) if get_col(row, "supplier_id") is not None else None,
        str(get_col(row, "feedback_id")) if get_col(row, "feedback_id") is not None else None,
        get_col(row, "review_date") or get_col(row, "date") or get_col(row, "created_at"),
        get_col(row, "source_dataset"),
        get_col(row, "text_column_source"),
        get_col(row, "classifier_embedding_model"),
        get_col(row, "classifier_model"),
        Json(raw_metadata),
    )


def main() -> None:
    if not POSTGRES_REVIEWS_PATH.exists():
        raise FileNotFoundError(
            f"Не найден файл {POSTGRES_REVIEWS_PATH}. Проверь POSTGRES_REVIEWS_PATH в .env"
        )

    print("Читаю:", POSTGRES_REVIEWS_PATH)
    df = pd.read_parquet(POSTGRES_REVIEWS_PATH)
    print("rows:", len(df))
    print("columns:", list(df.columns))

    required = {"review_id", "review_text", "predicted_labels"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"В файле не хватает колонок: {missing}")

    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            if TRUNCATE_BEFORE_LOAD:
                print("TRUNCATE reviews")
                cur.execute("TRUNCATE TABLE reviews;")

            for start in tqdm(range(0, len(df), BATCH_SIZE), desc="Loading PostgreSQL"):
                batch = df.iloc[start:start + BATCH_SIZE]
                values = [row_to_tuple(row) for _, row in batch.iterrows()]
                execute_values(cur, INSERT_SQL, values, page_size=BATCH_SIZE)
                conn.commit()

            cur.execute("SELECT COUNT(*) FROM reviews;")
            total = cur.fetchone()[0]
            print("reviews in PostgreSQL:", total)


if __name__ == "__main__":
    main()
