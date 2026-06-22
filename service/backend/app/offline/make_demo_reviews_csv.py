"""Создает маленький demo CSV, чтобы проверить сервис без реального датасета."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


DEMO_ROWS = [
    {
        "отзыв": "Книга пришла с мятой обложкой, упаковка была порвана.",
        "labels": "Упаковка | Брак/дефект товара",
        "review_date": "2025-09-01",
        "category": "Книги",
        "product_name": "Война и мир",
        "product_id": "book_001",
        "rating": "2",
    },
    {
        "отзыв": "Доставка задержалась на неделю, товар получила позже обещанного.",
        "labels": "Доставка/получение",
        "review_date": "2025-09-03",
        "category": "Книги",
        "product_name": "Анна Каренина",
        "product_id": "book_002",
        "rating": "3",
    },
    {
        "отзыв": "Обложка красивая, книга понравилась.",
        "labels": "Положительный отзыв",
        "review_date": "2025-09-05",
        "category": "Книги",
        "product_name": "Война и мир",
        "product_id": "book_001",
        "rating": "5",
    },
    {
        "отзыв": "Пришла не та книга, описание на карточке товара не совпадает.",
        "labels": "Несоответствие описанию",
        "review_date": "2025-10-02",
        "category": "Книги",
        "product_name": "Преступление и наказание",
        "product_id": "book_003",
        "rating": "1",
    },
    {
        "отзыв": "Страницы помяты, углы повреждены, упаковка слабая.",
        "labels": "Упаковка | Брак/дефект товара",
        "review_date": "2025-10-05",
        "category": "Книги",
        "product_name": "Война и мир",
        "product_id": "book_001",
        "rating": "2",
    },
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("demo_reviews.csv"))
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(DEMO_ROWS[0].keys()))
        writer.writeheader()
        writer.writerows(DEMO_ROWS)

    print(f"Demo CSV создан: {args.output}")


if __name__ == "__main__":
    main()
