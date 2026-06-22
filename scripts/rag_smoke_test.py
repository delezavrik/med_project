from __future__ import annotations

import os
from typing import Any

import psycopg2
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://reviews_user:reviews_password@localhost:5432/reviews_db")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "wb_reviews_bge_m3")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3")

QUERY = os.getenv("RAG_QUERY", "книга пришла с рваной обложкой")
TOP_K = int(os.getenv("RAG_TOP_K", "5"))

# Для e5-like моделей часто нужен prefix "query: ". Для bge-m3 обычно можно пустой.
QUERY_PREFIX = os.getenv("QUERY_PREFIX", "")


def fetch_reviews(review_ids: list[int]) -> dict[int, dict[str, Any]]:
    if not review_ids:
        return {}
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT review_id, review_text, predicted_labels_str, rating, category, brand
                FROM reviews
                WHERE review_id = ANY(%s);
                """,
                (review_ids,),
            )
            rows = cur.fetchall()
    return {
        int(r[0]): {
            "review_text": r[1],
            "predicted_labels_str": r[2],
            "rating": r[3],
            "category": r[4],
            "brand": r[5],
        }
        for r in rows
    }


def main() -> None:
    print("query:", QUERY)
    print("embedding model:", EMBEDDING_MODEL_NAME)
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    query_vector = model.encode([QUERY_PREFIX + QUERY], normalize_embeddings=True)[0].astype("float32").tolist()

    client = QdrantClient(url=QDRANT_URL)
    hits = client.search(
        collection_name=QDRANT_COLLECTION,
        query_vector=query_vector,
        limit=TOP_K,
        with_payload=True,
    )

    review_ids = [int(h.id) for h in hits]
    pg_reviews = fetch_reviews(review_ids)

    print("\nРезультаты:")
    for rank, hit in enumerate(hits, start=1):
        review_id = int(hit.id)
        pg = pg_reviews.get(review_id, {})
        print("=" * 80)
        print(f"#{rank} review_id={review_id} score={hit.score:.4f}")
        print("labels:", pg.get("predicted_labels_str") or hit.payload.get("predicted_labels_str"))
        print("rating:", pg.get("rating"), "category:", pg.get("category"), "brand:", pg.get("brand"))
        print("text:", (pg.get("review_text") or "")[:700])


if __name__ == "__main__":
    main()
