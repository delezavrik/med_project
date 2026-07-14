"""Канонический список меток классификатора и производные множества.

Основано на postgres_export_manifest.json (bge-m3 + LinearSVC_balanced + saved_thresholds).
Ровно 9 классов, используемых во всех местах (Postgres, Qdrant payload, frontend templates).
"""

POSITIVE_LABEL = "Положительный / нейтральный отзыв"

KNOWN_LABELS: list[str] = [
    POSITIVE_LABEL,
    "Проблема с качеством товара",
    "Проблема с размером / посадкой",
    "Проблема с комплектацией / упаковкой",
    "Несоответствие карточке товара",
    "Цена / ценность",
    "Проблема с возвратом",
    "Проблема доставки / получения",
    "Другая проблема",
]

PROBLEM_LABELS: list[str] = [label for label in KNOWN_LABELS if label != POSITIVE_LABEL]
