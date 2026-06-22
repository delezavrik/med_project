"""Импорт размеченного CSV с отзывами в PostgreSQL.

Минимальная цель MVP:
CSV с колонками "отзыв" и "labels" -> таблицы reviews и review_labels.

Пример локального запуска с Mac, когда Postgres из Docker проброшен на localhost:5433:

python -m app.offline.import_reviews_to_postgres \
  --input ../../labeled/wb_feedbacks_ChatGpt_markup_from_synthetic_gpt5_V_2/chatgpt_labeled_reviews_mvp_combined.csv \
  --dsn postgresql://reviews_user:reviews_password@localhost:5433/reviews_db \
  --init-schema \
  --default-date 2025-01-01 \
  --default-category "Тестовая категория"

Скрипт специально не использует pandas, чтобы не добавлять тяжелые зависимости.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import psycopg


TEXT_COLUMN_CANDIDATES = [
    "отзыв",
    "review",
    "review_text",
    "text",
    "comment",
    "feedback",
]

LABELS_COLUMN_CANDIDATES = [
    "labels",
    "new_labels",
    "correct_labels",
    "label",
    "problem_labels",
]

DATE_COLUMN_CANDIDATES = [
    "review_date",
    "date",
    "created_at",
    "dt",
]

PRODUCT_ID_COLUMN_CANDIDATES = [
    "product_id",
    "nm_id",
    "nmId",
    "sku",
    "item_id",
]

PRODUCT_NAME_COLUMN_CANDIDATES = [
    "product_name",
    "product",
    "subject_name",
    "name",
    "title",
]

BRAND_COLUMN_CANDIDATES = ["brand", "brand_name"]
CATEGORY_COLUMN_CANDIDATES = ["category", "category_name", "subject", "subject_name"]
RATING_COLUMN_CANDIDATES = ["rating", "rate", "stars", "valuation"]
SELLER_ID_COLUMN_CANDIDATES = ["seller_id", "supplier_id", "supplierId"]
REVIEW_ID_COLUMN_CANDIDATES = ["review_id", "feedback_id", "id", "uuid"]


@dataclass(frozen=True)
class ColumnMapping:
    text: str
    labels: str | None
    review_id: str | None
    review_date: str | None
    product_id: str | None
    product_name: str | None
    brand: str | None
    category: str | None
    rating: str | None
    seller_id: str | None


def find_column(fieldnames: list[str], candidates: list[str], explicit: str | None = None) -> str | None:
    if explicit:
        if explicit not in fieldnames:
            raise ValueError(f"Колонка '{explicit}' не найдена. Есть колонки: {fieldnames}")
        return explicit

    lowered = {name.lower().strip(): name for name in fieldnames}
    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    return None


def detect_mapping(
    fieldnames: list[str],
    text_column: str | None,
    labels_column: str | None,
) -> ColumnMapping:
    text = find_column(fieldnames, TEXT_COLUMN_CANDIDATES, text_column)
    if text is None:
        raise ValueError(
            "Не нашел колонку с текстом отзыва. "
            f"Передай --text-column. Есть колонки: {fieldnames}"
        )

    labels = find_column(fieldnames, LABELS_COLUMN_CANDIDATES, labels_column)

    return ColumnMapping(
        text=text,
        labels=labels,
        review_id=find_column(fieldnames, REVIEW_ID_COLUMN_CANDIDATES),
        review_date=find_column(fieldnames, DATE_COLUMN_CANDIDATES),
        product_id=find_column(fieldnames, PRODUCT_ID_COLUMN_CANDIDATES),
        product_name=find_column(fieldnames, PRODUCT_NAME_COLUMN_CANDIDATES),
        brand=find_column(fieldnames, BRAND_COLUMN_CANDIDATES),
        category=find_column(fieldnames, CATEGORY_COLUMN_CANDIDATES),
        rating=find_column(fieldnames, RATING_COLUMN_CANDIDATES),
        seller_id=find_column(fieldnames, SELLER_ID_COLUMN_CANDIDATES),
    )


def parse_labels(value: str | None) -> list[str]:
    if value is None:
        return []

    raw = str(value).strip()
    if not raw or raw.lower() in {"nan", "none", "null", "[]"}:
        return []

    # Поддержка JSON/Python-списков: ["Упаковка", "Доставка/получение"]
    if raw.startswith("[") and raw.endswith("]"):
        for parser in (json.loads, ast.literal_eval):
            try:
                parsed = parser(raw)
                if isinstance(parsed, list):
                    return normalize_labels(parsed)
            except Exception:  # noqa: BLE001
                pass

    # Поддержка строк: "Упаковка | Доставка/получение"
    if "|" in raw:
        return normalize_labels(raw.split("|"))
    if ";" in raw:
        return normalize_labels(raw.split(";"))
    if "," in raw:
        return normalize_labels(raw.split(","))

    return normalize_labels([raw])


def normalize_labels(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        label = str(value).strip().strip('"').strip("'")
        if not label or label.lower() in {"nan", "none", "null"}:
            continue
        if label not in seen:
            result.append(label)
            seen.add(label)
    return result


def parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw or raw.lower() in {"nan", "none", "null"}:
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


def parse_date(value: str | None, default_date: str | None) -> date | None:
    raw = str(value).strip() if value is not None else ""
    if not raw or raw.lower() in {"nan", "none", "null"}:
        raw = default_date or ""
    if not raw:
        return None

    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw[:19], fmt).date()
        except ValueError:
            continue

    # Последняя попытка: ISO-строка с временем.
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def get_value(row: dict[str, str], column: str | None, default: str | None = None) -> str | None:
    if column is None:
        return default
    value = row.get(column)
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip()


def build_review_id(row: dict[str, str], mapping: ColumnMapping, row_number: int) -> str:
    explicit_id = get_value(row, mapping.review_id)
    if explicit_id:
        return explicit_id

    text = get_value(row, mapping.text, "") or ""
    digest = hashlib.sha1(f"{row_number}:{text}".encode("utf-8")).hexdigest()[:16]
    return f"csv_{row_number}_{digest}"


def read_csv_rows(path: Path, delimiter: str | None) -> tuple[list[dict[str, str]], list[str]]:
    encodings = ["utf-8-sig", "utf-8", "cp1251"]
    last_error: Exception | None = None

    for encoding in encodings:
        try:
            with path.open("r", encoding=encoding, newline="") as file:
                sample = file.read(4096)
                file.seek(0)
                if delimiter:
                    dialect = csv.excel()
                    dialect.delimiter = delimiter
                else:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
                reader = csv.DictReader(file, dialect=dialect)
                if not reader.fieldnames:
                    raise ValueError("CSV не содержит header-строку с названиями колонок")
                rows = list(reader)
                return rows, list(reader.fieldnames)
        except Exception as exc:  # noqa: BLE001
            last_error = exc

    raise RuntimeError(f"Не удалось прочитать CSV: {last_error}")


def init_schema(conn: psycopg.Connection, schema_path: Path) -> None:
    if not schema_path.exists():
        raise FileNotFoundError(f"schema.sql не найден: {schema_path}")
    conn.execute(schema_path.read_text(encoding="utf-8"))
    conn.commit()


def import_rows(
    *,
    dsn: str,
    rows: list[dict[str, str]],
    mapping: ColumnMapping,
    default_date: str | None,
    default_category: str | None,
    default_brand: str | None,
    default_product_name: str | None,
    model_name: str,
    replace_labels: bool,
    init_schema_path: Path | None,
) -> dict[str, int]:
    inserted_reviews = 0
    inserted_labels = 0
    skipped_empty_text = 0

    with psycopg.connect(dsn) as conn:
        if init_schema_path is not None:
            init_schema(conn, init_schema_path)

        with conn.cursor() as cur:
            for idx, row in enumerate(rows, start=1):
                text = get_value(row, mapping.text)
                if not text:
                    skipped_empty_text += 1
                    continue

                review_id = build_review_id(row, mapping, idx)
                review_date = parse_date(get_value(row, mapping.review_date), default_date)
                rating = parse_int(get_value(row, mapping.rating))
                product_id = get_value(row, mapping.product_id)
                product_name = get_value(row, mapping.product_name, default_product_name)
                brand = get_value(row, mapping.brand, default_brand)
                category = get_value(row, mapping.category, default_category)
                seller_id = get_value(row, mapping.seller_id)
                labels = parse_labels(get_value(row, mapping.labels)) if mapping.labels else []

                cur.execute(
                    """
                    INSERT INTO reviews (
                        review_id,
                        review_date,
                        text,
                        rating,
                        product_id,
                        product_name,
                        brand,
                        category,
                        seller_id
                    )
                    VALUES (
                        %(review_id)s,
                        %(review_date)s,
                        %(text)s,
                        %(rating)s,
                        %(product_id)s,
                        %(product_name)s,
                        %(brand)s,
                        %(category)s,
                        %(seller_id)s
                    )
                    ON CONFLICT (review_id) DO UPDATE SET
                        review_date = EXCLUDED.review_date,
                        text = EXCLUDED.text,
                        rating = EXCLUDED.rating,
                        product_id = EXCLUDED.product_id,
                        product_name = EXCLUDED.product_name,
                        brand = EXCLUDED.brand,
                        category = EXCLUDED.category,
                        seller_id = EXCLUDED.seller_id;
                    """,
                    {
                        "review_id": review_id,
                        "review_date": review_date,
                        "text": text,
                        "rating": rating,
                        "product_id": product_id,
                        "product_name": product_name,
                        "brand": brand,
                        "category": category,
                        "seller_id": seller_id,
                    },
                )
                inserted_reviews += 1

                if replace_labels:
                    cur.execute("DELETE FROM review_labels WHERE review_id = %s", (review_id,))

                for label in labels:
                    cur.execute(
                        """
                        INSERT INTO review_labels (review_id, label, confidence, model_name)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (review_id, label) DO UPDATE SET
                            confidence = EXCLUDED.confidence,
                            model_name = EXCLUDED.model_name;
                        """,
                        (review_id, label, None, model_name),
                    )
                    inserted_labels += 1

        conn.commit()

    return {
        "reviews_upserted": inserted_reviews,
        "labels_upserted": inserted_labels,
        "skipped_empty_text": skipped_empty_text,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Импорт CSV с отзывами в PostgreSQL")
    parser.add_argument("--input", required=True, type=Path, help="Путь к CSV")
    parser.add_argument(
        "--dsn",
        default=os.getenv("POSTGRES_DSN"),
        help="PostgreSQL DSN. Например: postgresql://reviews_user:reviews_password@localhost:5433/reviews_db",
    )
    parser.add_argument("--text-column", default=None, help="Название колонки с текстом отзыва")
    parser.add_argument("--labels-column", default=None, help="Название колонки с labels")
    parser.add_argument("--delimiter", default=None, help="Разделитель CSV, если автоопределение ошиблось")
    parser.add_argument("--default-date", default=None, help="Дата по умолчанию YYYY-MM-DD, если в CSV нет даты")
    parser.add_argument("--default-category", default=None, help="Категория по умолчанию, если в CSV нет category")
    parser.add_argument("--default-brand", default=None, help="Бренд по умолчанию, если в CSV нет brand")
    parser.add_argument("--default-product-name", default=None, help="Товар по умолчанию, если в CSV нет product_name")
    parser.add_argument("--model-name", default="imported_labels", help="model_name для review_labels")
    parser.add_argument("--keep-old-labels", action="store_true", help="Не удалять старые labels при повторном импорте")
    parser.add_argument(
        "--init-schema",
        action="store_true",
        help="Перед импортом выполнить backend/sql/schema.sql",
    )
    args = parser.parse_args()

    if not args.dsn:
        raise ValueError("Не задан DSN. Передай --dsn или переменную POSTGRES_DSN")
    if not args.input.exists():
        raise FileNotFoundError(args.input)

    rows, fieldnames = read_csv_rows(args.input, args.delimiter)
    mapping = detect_mapping(fieldnames, args.text_column, args.labels_column)

    schema_path = None
    if args.init_schema:
        schema_path = Path(__file__).resolve().parents[3] / "sql" / "schema.sql"

    print("Найдены колонки CSV:")
    print(fieldnames)
    print("\nИспользуем mapping:")
    print(mapping)
    print(f"\nСтрок в CSV: {len(rows)}")

    stats = import_rows(
        dsn=args.dsn,
        rows=rows,
        mapping=mapping,
        default_date=args.default_date,
        default_category=args.default_category,
        default_brand=args.default_brand,
        default_product_name=args.default_product_name,
        model_name=args.model_name,
        replace_labels=not args.keep_old_labels,
        init_schema_path=schema_path,
    )

    print("\nИмпорт завершен:")
    for key, value in stats.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
