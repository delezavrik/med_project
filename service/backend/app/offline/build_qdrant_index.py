"""Заготовка для построения Qdrant-индекса отзывов.

Здесь должна использоваться та же embedding-модель, что и в online QdrantTool._embed().
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--collection", default="reviews_embeddings")
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(args.input)

    print("TODO: построить эмбеддинги, создать collection и загрузить payload в Qdrant")
    print(f"input={args.input}")
    print(f"collection={args.collection}")


if __name__ == "__main__":
    main()
