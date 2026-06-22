from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from tqdm.auto import tqdm

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "wb_reviews_bge_m3")
QDRANT_VECTORS_PATH = Path(os.getenv("QDRANT_VECTORS_PATH", "data/db_exports/qdrant_vectors_baai_bge_m3/qdrant_vectors.npy"))
QDRANT_PAYLOAD_PATH = Path(os.getenv("QDRANT_PAYLOAD_PATH", "data/db_exports/qdrant_vectors_baai_bge_m3/qdrant_payload.parquet"))
BATCH_SIZE = int(os.getenv("QDRANT_LOAD_BATCH_SIZE", "1000"))
RECREATE_COLLECTION = os.getenv("RECREATE_QDRANT_COLLECTION", "0") == "1"


def clean_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and np.isnan(value):
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value):
            return None
        return float(value)
    if isinstance(value, np.ndarray):
        return [clean_value(x) for x in value.tolist()]
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return None
        return value.isoformat()
    if isinstance(value, list):
        return [clean_value(x) for x in value]
    if isinstance(value, dict):
        return {str(k): clean_value(v) for k, v in value.items()}
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return value


def parse_maybe_list(value: Any) -> Any:
    value = clean_value(value)
    if value is None:
        return None
    if isinstance(value, list):
        return value
    s = str(value).strip()
    if not s:
        return []
    try:
        parsed = json.loads(s)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass
    if "|" in s:
        return [x.strip() for x in s.split("|") if x.strip()]
    return [s]


def row_to_payload(row: pd.Series) -> dict[str, Any]:
    payload = {}
    for col, value in row.items():
        value = clean_value(value)
        if value is None:
            continue
        if col == "predicted_labels":
            value = parse_maybe_list(value)
        payload[col] = value
    return payload


def main() -> None:
    if not QDRANT_VECTORS_PATH.exists():
        raise FileNotFoundError(f"Не найден {QDRANT_VECTORS_PATH}. Проверь QDRANT_VECTORS_PATH в .env")
    if not QDRANT_PAYLOAD_PATH.exists():
        raise FileNotFoundError(f"Не найден {QDRANT_PAYLOAD_PATH}. Проверь QDRANT_PAYLOAD_PATH в .env")

    print("QDRANT_URL:", QDRANT_URL)
    print("QDRANT_COLLECTION:", QDRANT_COLLECTION)
    print("vectors:", QDRANT_VECTORS_PATH)
    print("payload:", QDRANT_PAYLOAD_PATH)

    vectors = np.load(QDRANT_VECTORS_PATH, mmap_mode="r")
    payload_df = pd.read_parquet(QDRANT_PAYLOAD_PATH)

    if len(vectors) != len(payload_df):
        raise ValueError(f"vectors rows={len(vectors)} != payload rows={len(payload_df)}")
    if "review_id" not in payload_df.columns:
        raise ValueError("В qdrant_payload.parquet нет колонки review_id")

    vector_dim = int(vectors.shape[1])
    print("n_vectors:", len(vectors))
    print("vector_dim:", vector_dim)

    client = QdrantClient(url=QDRANT_URL)

    existing = [c.name for c in client.get_collections().collections]
    if QDRANT_COLLECTION in existing and RECREATE_COLLECTION:
        print("Удаляю старую collection:", QDRANT_COLLECTION)
        client.delete_collection(QDRANT_COLLECTION)
        existing.remove(QDRANT_COLLECTION)

    if QDRANT_COLLECTION not in existing:
        print("Создаю collection:", QDRANT_COLLECTION)
        client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=vector_dim, distance=Distance.COSINE),
        )
    else:
        info = client.get_collection(QDRANT_COLLECTION)
        print("Collection уже есть:", info.status)

    for start in tqdm(range(0, len(payload_df), BATCH_SIZE), desc="Loading Qdrant"):
        end = min(start + BATCH_SIZE, len(payload_df))
        batch_payload = payload_df.iloc[start:end]
        batch_vectors = vectors[start:end]

        points = []
        for i, (_, row) in enumerate(batch_payload.iterrows()):
            review_id = int(row["review_id"])
            points.append(
                PointStruct(
                    id=review_id,
                    vector=batch_vectors[i].astype("float32").tolist(),
                    payload=row_to_payload(row),
                )
            )

        client.upsert(collection_name=QDRANT_COLLECTION, points=points, wait=True)

    info = client.get_collection(QDRANT_COLLECTION)
    print("Qdrant points_count:", info.points_count)
    print("Готово")


if __name__ == "__main__":
    main()
