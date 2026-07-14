"""Оркестратор загрузки экспортов в Postgres и Qdrant.

Пример запуска:
    python -m app.offline.load_db_exports --target all
    python -m app.offline.load_db_exports --target postgres --truncate-postgres
    python -m app.offline.load_db_exports --target qdrant --recreate-qdrant

Пути к экспортам берутся из env:
    POSTGRES_DSN, QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION,
    POSTGRES_EXPORT_DIR, QDRANT_EXPORT_DIR

Ожидаемая структура:
    POSTGRES_EXPORT_DIR/reviews_for_postgres.csv
    QDRANT_EXPORT_DIR/qdrant_manifest.json
    QDRANT_EXPORT_DIR/qdrant_vectors.npy       (или vector_parts/*.npy)
    QDRANT_EXPORT_DIR/qdrant_payload.csv
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable

import psycopg


# Postgres и Qdrant CSV могут содержать очень длинные review_text и description.
csv.field_size_limit(sys.maxsize)


# --- Postgres --------------------------------------------------------------


def _truncate_postgres(dsn: str) -> None:
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE review_labels, reviews RESTART IDENTITY CASCADE;")
    print("Postgres: таблицы reviews и review_labels очищены.")


def _load_postgres(dsn: str, csv_path: Path, truncate: bool) -> None:
    if truncate:
        _truncate_postgres(dsn)

    # Делегируем существующему импортёру через sys.argv, чтобы не дублировать логику.
    from app.offline import import_reviews_to_postgres as importer

    # NB: --init-schema не передаём — схема грузится Postgres-контейнером при старте
    # (см. docker-compose.dev.yml: bind-mount backend/sql/schema.sql в /docker-entrypoint-initdb.d).
    # Так же аккуратнее для локальных запусков вне docker.
    # --labels-column = predicted_labels_str (pipe-separated), а не predicted_labels (numpy-repr
    # без запятых, importer его не распарсит и склеит метки в одну строку).
    saved_argv = sys.argv
    sys.argv = [
        "import_reviews_to_postgres",
        "--input", str(csv_path),
        "--dsn", dsn,
        "--labels-column", "predicted_labels_str",
    ]
    try:
        importer.main()
    finally:
        sys.argv = saved_argv


# --- Qdrant ----------------------------------------------------------------


def _parse_labels(raw: str | None) -> list[str]:
    if raw is None:
        return []
    raw = raw.strip()
    if not raw or raw in {"[]", "nan", "None", "null"}:
        return []
    if raw.startswith("["):
        try:
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except (SyntaxError, ValueError):
            pass
    # Pipe-separated (predicted_labels_str). Проверяем ДО запятой, потому что
    # у меток самих внутри есть запятые ("Проблема с размером / посадкой" не имеет,
    # но "Положительный / нейтральный отзыв" в теории может).
    if "|" in raw:
        return [item.strip() for item in raw.split("|") if item.strip()]
    if ";" in raw:
        return [item.strip() for item in raw.split(";") if item.strip()]
    return [raw]


def _parse_int(raw: str | None) -> int | None:
    if raw is None or raw == "":
        return None
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


def _normalize_review_date(raw: str | None) -> str | None:
    """Приводит дату к ISO-строке с суффиксом T00:00:00Z для Qdrant DatetimeRange."""
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    if "T" in raw:
        return raw if raw.endswith("Z") else f"{raw}Z"
    return f"{raw}T00:00:00Z"


def _load_qdrant_vectors(export_dir: Path):
    import numpy as np

    single = export_dir / "qdrant_vectors.npy"
    if single.exists():
        print(f"Qdrant: читаю векторы из {single.name}...")
        return np.load(single, mmap_mode="r")

    parts_dir = export_dir / "vector_parts"
    if not parts_dir.exists():
        raise FileNotFoundError(
            f"Не нашёл qdrant_vectors.npy и {parts_dir}. Проверь QDRANT_EXPORT_DIR."
        )
    part_files = sorted(parts_dir.glob("vectors_part_*.npy"))
    if not part_files:
        raise FileNotFoundError(f"В {parts_dir} нет файлов vectors_part_*.npy")
    print(f"Qdrant: конкатенирую {len(part_files)} частей...")
    return np.concatenate([np.load(p) for p in part_files], axis=0)


def _iter_payload_rows(csv_path: Path) -> Iterable[dict[str, Any]]:
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Приоритет predicted_labels_str (pipe-separated, чистый) — колонка
            # predicted_labels в CSV сохранена как numpy-repr без запятых, парсер её порвёт.
            labels = _parse_labels(row.get("predicted_labels_str")) or _parse_labels(
                row.get("predicted_labels")
            )
            yield {
                "review_id": _parse_int(row.get("review_id")),
                "predicted_labels": labels,
                "review_text": row.get("review_text_preview") or "",
                "review_date": _normalize_review_date(row.get("review_date")),
                "rating": _parse_int(row.get("rating")),
                "product_id": row.get("product_id") or None,
                "product_name": row.get("product_name") or None,
                "category": row.get("category") or None,
                "brand": row.get("brand") or None,
            }


def _load_qdrant(
    url: str,
    api_key: str | None,
    collection: str,
    export_dir: Path,
    recreate: bool,
    batch_size: int,
) -> None:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qm

    manifest_path = export_dir / "qdrant_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    dim = int(manifest["vector_dim"])
    expected = int(manifest.get("n_reviews", 0))
    print(f"Qdrant: manifest dim={dim}, ожидается {expected} записей.")

    vectors = _load_qdrant_vectors(export_dir)
    if vectors.shape[1] != dim:
        raise ValueError(f"Векторы размерности {vectors.shape[1]}, а в manifest {dim}.")

    client = QdrantClient(url=url, api_key=api_key or None, timeout=60)

    collections = {c.name for c in client.get_collections().collections}
    if collection in collections and recreate:
        print(f"Qdrant: удаляю существующую коллекцию {collection}...")
        client.delete_collection(collection)
        collections.discard(collection)

    if collection not in collections:
        print(f"Qdrant: создаю коллекцию {collection} (dim={dim}, cosine)...")
        client.create_collection(
            collection_name=collection,
            vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
        )
        # Индексы для фильтров, которыми пользуется qdrant_tool.
        for field, schema in (
            ("predicted_labels", qm.PayloadSchemaType.KEYWORD),
            ("category", qm.PayloadSchemaType.KEYWORD),
            ("brand", qm.PayloadSchemaType.KEYWORD),
            ("product_id", qm.PayloadSchemaType.KEYWORD),
            ("product_name", qm.PayloadSchemaType.TEXT),
            ("rating", qm.PayloadSchemaType.INTEGER),
            ("review_date", qm.PayloadSchemaType.DATETIME),
        ):
            client.create_payload_index(collection, field_name=field, field_schema=schema)
        print("Qdrant: payload-индексы созданы.")

    payload_csv = export_dir / "qdrant_payload.csv"
    if not payload_csv.exists():
        raise FileNotFoundError(payload_csv)

    print(f"Qdrant: загружаю точки батчами по {batch_size}...")
    batch_ids: list[int] = []
    batch_vecs: list[list[float]] = []
    batch_payloads: list[dict[str, Any]] = []
    uploaded = 0

    for i, payload in enumerate(_iter_payload_rows(payload_csv)):
        if i >= vectors.shape[0]:
            print(
                f"Qdrant: payload CSV длиннее vectors ({vectors.shape[0]}), остаток пропускаю."
            )
            break
        review_id = payload["review_id"]
        if review_id is None:
            review_id = i + 1
        batch_ids.append(int(review_id))
        batch_vecs.append(vectors[i].astype("float32").tolist())
        batch_payloads.append(payload)

        if len(batch_ids) >= batch_size:
            client.upsert(
                collection_name=collection,
                points=qm.Batch(ids=batch_ids, vectors=batch_vecs, payloads=batch_payloads),
                wait=False,
            )
            uploaded += len(batch_ids)
            batch_ids, batch_vecs, batch_payloads = [], [], []
            if uploaded % (batch_size * 10) == 0:
                print(f"  ... загружено {uploaded}")

    if batch_ids:
        client.upsert(
            collection_name=collection,
            points=qm.Batch(ids=batch_ids, vectors=batch_vecs, payloads=batch_payloads),
            wait=True,
        )
        uploaded += len(batch_ids)

    print(f"Qdrant: загружено {uploaded} точек в коллекцию {collection}.")


# --- CLI -------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Оркестратор загрузки экспортов в Postgres и Qdrant.")
    parser.add_argument("--target", choices=("all", "postgres", "qdrant"), default="all")
    parser.add_argument("--truncate-postgres", action="store_true")
    parser.add_argument("--recreate-qdrant", action="store_true")
    parser.add_argument("--qdrant-batch", type=int, default=500)
    parser.add_argument("--postgres-dsn", default=os.getenv("POSTGRES_DSN"))
    parser.add_argument("--qdrant-url", default=os.getenv("QDRANT_URL"))
    parser.add_argument("--qdrant-api-key", default=os.getenv("QDRANT_API_KEY"))
    parser.add_argument("--qdrant-collection", default=os.getenv("QDRANT_COLLECTION", "wb_reviews_bge_m3"))
    parser.add_argument(
        "--postgres-export-dir",
        type=Path,
        default=Path(os.getenv("POSTGRES_EXPORT_DIR", "/app/data/db_exports/postgres_reviews_bge_m3_linearsvc_saved_model")),
    )
    parser.add_argument(
        "--qdrant-export-dir",
        type=Path,
        default=Path(os.getenv("QDRANT_EXPORT_DIR", "/app/data/db_exports/qdrant_vectors_baai_bge_m3")),
    )
    args = parser.parse_args()

    if args.target in ("all", "postgres"):
        if not args.postgres_dsn:
            raise SystemExit("POSTGRES_DSN не задан.")
        csv_path = args.postgres_export_dir / "reviews_for_postgres.csv"
        if not csv_path.exists():
            raise SystemExit(f"Нет файла экспорта Postgres: {csv_path}")
        print(f"=== Postgres: загрузка из {csv_path} ===")
        _load_postgres(args.postgres_dsn, csv_path, truncate=args.truncate_postgres)

    if args.target in ("all", "qdrant"):
        if not args.qdrant_url:
            raise SystemExit("QDRANT_URL не задан.")
        print(f"=== Qdrant: загрузка из {args.qdrant_export_dir} ===")
        _load_qdrant(
            url=args.qdrant_url,
            api_key=args.qdrant_api_key,
            collection=args.qdrant_collection,
            export_dir=args.qdrant_export_dir,
            recreate=args.recreate_qdrant,
            batch_size=args.qdrant_batch,
        )

    print("Готово.")


if __name__ == "__main__":
    main()
