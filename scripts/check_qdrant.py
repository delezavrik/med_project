from __future__ import annotations

import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient

load_dotenv()
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "wb_reviews_bge_m3")

client = QdrantClient(url=QDRANT_URL)
print("collections:", [c.name for c in client.get_collections().collections])
info = client.get_collection(QDRANT_COLLECTION)
print(info)

points, _ = client.scroll(collection_name=QDRANT_COLLECTION, limit=3, with_payload=True, with_vectors=False)
for p in points:
    print("\npoint id:", p.id)
    print(p.payload)
