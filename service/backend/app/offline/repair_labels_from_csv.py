from __future__ import annotations

import argparse
import csv
import os
from collections import Counter
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values


KNOWN_LABELS = [
    "Положительный / нейтральный отзыв",
    "Проблема с размером / посадкой",
    "Проблема с качеством товара",
    "Проблема с комплектацией / упаковкой",
    "Несоответствие карточке товара",
    "Цена / ценность",
    "Проблема с возвратом",
    "Проблема доставки / получения",
    "Другая проблема",
]


def clean_col_name(name: str) -> str:
    return name.lstrip("\ufeff").strip()


def parse_labels(value: str | None) -> list[str]:
    if value is None:
        return []

    s = str(value).strip()
    if not s:
        return []

    found = []
    for label in KNOWN_LABELS:
        if label in s:
            found.append(label)

    # Дубликаты убираем, порядок сохраняем.
    return list(dict.fromkeys(found))


def get_table_columns(conn, table_name: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s;
            """,
            (table_name,),
        )
        return {row[0] for row in cur.fetchall()}


def print_label_stats(conn, title: str) -> None:
    print(f"\n=== {title} ===")
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT label, COUNT(DISTINCT review_id) AS review_count
            FROM review_labels
            GROUP BY label
            ORDER BY review_count DESC
            LIMIT 50;
            """
        )
        for label, count in cur.fetchall():
            print(f"{label}\t{count}")


def read_labels_from_csv(path: Path, labels_column: str) -> tuple[list[tuple[str, str]], Counter, Counter]:
    rows: list[tuple[str, str]] = []
    label_counter: Counter = Counter()
    unknown_counter: Counter = Counter()

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [clean_col_name(c) for c in reader.fieldnames or []]

        if "review_id" not in reader.fieldnames:
            raise ValueError(f"В CSV нет колонки review_id. Колонки: {reader.fieldnames}")

        if labels_column not in reader.fieldnames:
            raise ValueError(f"В CSV нет колонки {labels_column}. Колонки: {reader.fieldnames}")

        for row in reader:
            review_id = str(row.get("review_id", "")).strip()
            raw_labels = row.get(labels_column)

            if not review_id:
                continue

            labels = parse_labels(raw_labels)

            if not labels:
                unknown_counter[str(raw_labels).strip()] += 1
                continue

            for label in labels:
                rows.append((review_id, label))
                label_counter[label] += 1

    return rows, label_counter, unknown_counter


def repair_labels(conn, rows: list[tuple[str, str]], model_name: str, chunk_size: int = 10_000) -> None:
    review_label_columns = get_table_columns(conn, "review_labels")

    insert_columns = ["review_id", "label"]

    if "confidence" in review_label_columns:
        insert_columns.append("confidence")

    if "model_name" in review_label_columns:
        insert_columns.append("model_name")

    select_values = ["t.review_id", "t.label"]

    if "confidence" in review_label_columns:
        select_values.append("1.0")

    if "model_name" in review_label_columns:
        select_values.append("%s")

    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TEMP TABLE tmp_repaired_labels (
                review_id text,
                label text
            ) ON COMMIT DROP;
            """
        )

        for i in range(0, len(rows), chunk_size):
            chunk = rows[i : i + chunk_size]
            execute_values(
                cur,
                """
                INSERT INTO tmp_repaired_labels (review_id, label)
                VALUES %s;
                """,
                chunk,
            )

        cur.execute("DELETE FROM review_labels;")

        sql = f"""
            INSERT INTO review_labels ({", ".join(insert_columns)})
            SELECT DISTINCT {", ".join(select_values)}
            FROM tmp_repaired_labels t
            JOIN reviews r ON r.review_id = t.review_id
            ON CONFLICT DO NOTHING;
        """

        if "model_name" in review_label_columns:
            cur.execute(sql, (model_name,))
        else:
            cur.execute(sql)

    conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="CSV с review_id и predicted_labels_str")
    parser.add_argument(
        "--dsn",
        default=os.getenv("POSTGRES_DSN", "postgresql://reviews_user:reviews_password@postgres:5432/reviews_db"),
    )
    parser.add_argument("--labels-column", default="predicted_labels_str")
    parser.add_argument("--model-name", default="repaired_from_predicted_labels_str")
    args = parser.parse_args()

    path = Path(args.input)
    if not path.exists():
        raise FileNotFoundError(path)

    print(f"Читаю CSV: {path}")
    rows, label_counter, unknown_counter = read_labels_from_csv(path, args.labels_column)

    print(f"\nНайдено label-связей в CSV: {len(rows)}")
    print("\nРаспределение labels из CSV:")
    for label, count in label_counter.most_common():
        print(f"{label}\t{count}")

    if unknown_counter:
        print("\nСтроки без известных labels, top-20:")
        for value, count in unknown_counter.most_common(20):
            print(f"{repr(value)}\t{count}")

    conn = psycopg2.connect(args.dsn)

    try:
        print_label_stats(conn, "Labels ДО исправления")
        repair_labels(conn, rows, args.model_name)
        print_label_stats(conn, "Labels ПОСЛЕ исправления")
    finally:
        conn.close()

    print("\nГотово. Таблица review_labels пересобрана. Таблица reviews не трогалась.")


if __name__ == "__main__":
    main()