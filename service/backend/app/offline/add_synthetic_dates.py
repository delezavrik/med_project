from __future__ import annotations

import ast
import calendar
import hashlib
from pathlib import Path
from typing import List

import pandas as pd


# Запускать из корня проекта: ~/Documents/med_project
POSTGRES_CSV = Path("data/db_exports/postgres_reviews_bge_m3_linearsvc_saved_model/reviews_for_postgres.csv")
POSTGRES_PARQUET = Path("data/db_exports/postgres_reviews_bge_m3_linearsvc_saved_model/reviews_for_postgres.parquet")

QDRANT_CSV = Path("data/db_exports/qdrant_vectors_baai_bge_m3/qdrant_payload.csv")
QDRANT_PARQUET = Path("data/db_exports/qdrant_vectors_baai_bge_m3/qdrant_payload.parquet")


LABEL_PRIORITY = [
    "Проблема доставки / получения",
    "Проблема с возвратом",
    "Проблема с качеством товара",
    "Проблема с комплектацией / упаковкой",
    "Проблема с размером / посадкой",
    "Несоответствие карточке товара",
    "Цена / ценность",
    "Другая проблема",
    "Положительный / нейтральный отзыв",
]

# Распределение по месяцам: сентябрь / октябрь / ноябрь 2025
LABEL_MONTH_WEIGHTS = {
    "Положительный / нейтральный отзыв": {
        "2025-09": 0.34,
        "2025-10": 0.33,
        "2025-11": 0.33,
    },
    "Проблема с размером / посадкой": {
        "2025-09": 0.50,
        "2025-10": 0.30,
        "2025-11": 0.20,
    },
    "Проблема с качеством товара": {
        "2025-09": 0.20,
        "2025-10": 0.30,
        "2025-11": 0.50,
    },
    "Проблема с комплектацией / упаковкой": {
        "2025-09": 0.15,
        "2025-10": 0.60,
        "2025-11": 0.25,
    },
    "Несоответствие карточке товара": {
        "2025-09": 0.25,
        "2025-10": 0.50,
        "2025-11": 0.25,
    },
    "Цена / ценность": {
        "2025-09": 0.35,
        "2025-10": 0.35,
        "2025-11": 0.30,
    },
    "Проблема с возвратом": {
        "2025-09": 0.20,
        "2025-10": 0.25,
        "2025-11": 0.55,
    },
    "Проблема доставки / получения": {
        "2025-09": 0.15,
        "2025-10": 0.25,
        "2025-11": 0.60,
    },
    "Другая проблема": {
        "2025-09": 0.33,
        "2025-10": 0.33,
        "2025-11": 0.34,
    },
}


def remove_bom_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.lstrip("\ufeff") for c in df.columns]
    return df


def unit_hash(value: str) -> float:
    h = hashlib.md5(value.encode("utf-8")).hexdigest()
    n = int(h[:12], 16)
    return n / float(16**12 - 1)


def parse_labels(value) -> List[str]:
    if pd.isna(value):
        return []

    s = str(value).strip()
    if not s:
        return []

    # Попытка разобрать строку вида "['a', 'b']"
    if s.startswith("[") and s.endswith("]"):
        try:
            parsed = ast.literal_eval(s)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass

    # Обычная строка
    s = s.replace(";", ",").replace("|", ",")
    return [part.strip() for part in s.split(",") if part.strip()]


def choose_primary_label(labels: List[str]) -> str:
    if not labels:
        return "Положительный / нейтральный отзыв"

    label_set = set(labels)
    for label in LABEL_PRIORITY:
        if label in label_set:
            return label

    return labels[0]


def choose_month(review_id: str, label: str) -> str:
    weights = LABEL_MONTH_WEIGHTS.get(
        label,
        {"2025-09": 0.34, "2025-10": 0.33, "2025-11": 0.33},
    )

    u = unit_hash(f"{review_id}|month")
    cumulative = 0.0

    for month_key, weight in weights.items():
        cumulative += weight
        if u <= cumulative:
            return month_key

    return "2025-11"


def choose_day(review_id: str, year: int, month: int) -> int:
    days_in_month = calendar.monthrange(year, month)[1]
    u = unit_hash(f"{review_id}|day")
    return 1 + int(u * days_in_month)


def generate_date(review_id: str, primary_label: str) -> str:
    month_key = choose_month(review_id, primary_label)
    year, month = map(int, month_key.split("-"))
    day = choose_day(review_id, year, month)
    return f"{year:04d}-{month:02d}-{day:02d}"


def add_dates_to_postgres_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Не найден файл: {path}")

    df = pd.read_csv(path)
    df = remove_bom_columns(df)

    required_cols = {"review_id", "predicted_labels_str"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"В {path} нет колонок: {sorted(missing)}")

    primary_labels = []
    review_dates = []

    for row in df.itertuples(index=False):
        review_id = str(getattr(row, "review_id"))
        labels_raw = getattr(row, "predicted_labels_str")
        labels = parse_labels(labels_raw)
        primary_label = choose_primary_label(labels)
        review_date = generate_date(review_id, primary_label)

        primary_labels.append(primary_label)
        review_dates.append(review_date)

    df["review_date"] = review_dates
    df.to_csv(path, index=False, encoding="utf-8-sig")

    # Для статистики
    stat_df = pd.DataFrame({
        "primary_label": primary_labels,
        "review_date": review_dates,
    })
    stat_df["month"] = stat_df["review_date"].str.slice(0, 7)

    print(f"[OK] Обновлен CSV: {path}")
    print(f"rows: {len(df)}")
    print(f"min_date: {df['review_date'].min()}")
    print(f"max_date: {df['review_date'].max()}")
    print("\nРаспределение по месяцам:")
    print(stat_df["month"].value_counts().sort_index().to_string())
    print("\nРаспределение label x month:")
    pivot = pd.crosstab(stat_df["primary_label"], stat_df["month"])
    print(pivot.to_string())

    return df[["review_id", "review_date"]].copy()


def update_postgres_parquet(path: Path, date_map_df: pd.DataFrame) -> None:
    if not path.exists():
        print(f"[SKIP] Parquet не найден: {path}")
        return

    try:
        df = pd.read_parquet(path)
        df = remove_bom_columns(df)

        if "review_id" not in df.columns:
            raise ValueError("В parquet нет колонки review_id")

        df = df.drop(columns=["review_date"], errors="ignore")
        df = df.merge(date_map_df, on="review_id", how="left")
        df.to_parquet(path, index=False)

        print(f"[OK] Обновлен Parquet: {path}")
    except Exception as e:
        print(f"[WARN] Не удалось обновить parquet {path}: {e}")


def add_dates_to_qdrant_csv(path: Path, date_map_df: pd.DataFrame) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Не найден файл: {path}")

    df = pd.read_csv(path)
    df = remove_bom_columns(df)

    if "review_id" not in df.columns:
        raise ValueError(f"В {path} нет колонки review_id")

    df = df.drop(columns=["review_date"], errors="ignore")
    df = df.merge(date_map_df, on="review_id", how="left")

    matched = df["review_date"].notna().sum()
    unmatched = len(df) - matched

    df.to_csv(path, index=False, encoding="utf-8-sig")

    print(f"[OK] Обновлен CSV: {path}")
    print(f"rows: {len(df)}")
    print(f"matched review_date: {matched}")
    print(f"unmatched review_date: {unmatched}")


def update_qdrant_parquet(path: Path, date_map_df: pd.DataFrame) -> None:
    if not path.exists():
        print(f"[SKIP] Parquet не найден: {path}")
        return

    try:
        df = pd.read_parquet(path)
        df = remove_bom_columns(df)

        if "review_id" not in df.columns:
            raise ValueError("В parquet нет колонки review_id")

        df = df.drop(columns=["review_date"], errors="ignore")
        df = df.merge(date_map_df, on="review_id", how="left")
        df.to_parquet(path, index=False)

        matched = df["review_date"].notna().sum()
        unmatched = len(df) - matched

        print(f"[OK] Обновлен Parquet: {path}")
        print(f"matched review_date: {matched}")
        print(f"unmatched review_date: {unmatched}")
    except Exception as e:
        print(f"[WARN] Не удалось обновить parquet {path}: {e}")


def main():
    print("=== 1. Добавляем review_date в reviews_for_postgres ===")
    date_map_df = add_dates_to_postgres_csv(POSTGRES_CSV)

    print("\n=== 2. Обновляем reviews_for_postgres.parquet ===")
    update_postgres_parquet(POSTGRES_PARQUET, date_map_df)

    print("\n=== 3. Добавляем review_date в qdrant_payload ===")
    add_dates_to_qdrant_csv(QDRANT_CSV, date_map_df)

    print("\n=== 4. Обновляем qdrant_payload.parquet ===")
    update_qdrant_parquet(QDRANT_PARQUET, date_map_df)

    print("\nГотово.")
    print("Изменены те же самые файлы, имена не менялись, добавлено только поле review_date.")


if __name__ == "__main__":
    main()