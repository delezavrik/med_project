from qdrant_client import QdrantClient

from app.core.config import get_settings
from app.domain.labels import KNOWN_LABELS
from app.schemas.query import ParsedQuery, ReviewExample, StructuredResult


class QdrantTool:
    """Инструмент для semantic search по отзывам.

    В MVP метод `_embed` оставлен как точка расширения.
    Его можно заменить на локальную embedding-модель или внешний embedding API.
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def run(self, query: ParsedQuery) -> StructuredResult:
        result = StructuredResult(parsed_query=query)

        if not self.settings.qdrant_url:
            result.warnings.append("QDRANT_URL не задан. Qdrant-инструмент не был выполнен.")
            return result

        if not query.semantic_query:
            result.warnings.append("semantic_query пустой. Для Qdrant-поиска нужен текстовый запрос.")
            return result

        try:
            client = QdrantClient(url=self.settings.qdrant_url, api_key=self.settings.qdrant_api_key or None)
            vector = self._embed(query.semantic_query)
            # Чистый семантический поиск без payload-фильтра: поля payload не
            # проиндексированы под фильтрацию, а смысловой запрос сам таргетирует релевантные отзывы.
            hits = client.search(
                collection_name=self.settings.qdrant_collection,
                query_vector=vector,
                limit=query.limit,
                with_payload=True,
            )
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Ошибка Qdrant-инструмента: {exc}")
            return result

        for hit in hits:
            payload = hit.payload or {}
            labels = payload.get("predicted_labels") or payload.get("labels") or []
            if isinstance(labels, str):
                labels = [labels]
            labels = [label for label in labels if label in KNOWN_LABELS]

            rating = payload.get("rating")
            if not isinstance(rating, int) or not (1 <= rating <= 5):
                rating = None

            result.examples.append(
                ReviewExample(
                    review_id=str(payload.get("review_id") or hit.id),
                    text=str(payload.get("review_text") or payload.get("text") or ""),
                    labels=list(labels),
                    product_name=payload.get("product_name"),
                    rating=rating,
                    date=str(payload.get("review_date"))[:10] if payload.get("review_date") else None,
                    score=float(hit.score) if hit.score is not None else None,
                )
            )

        result.raw["trace_steps"] = [
            {"id": "embed", "title": "Векторизовал запрос (BGE-M3)", "status": "ok", "duration_ms": None,
             "input": {"semantic_query": query.semantic_query}, "output": {"dim": len(vector)}},
            {"id": "qdrant", "title": "Семантический поиск в Qdrant", "status": "ok", "duration_ms": None,
             "input": {"limit": query.limit}, "output": {"found": len(result.examples)}},
        ]
        return result

    def _embed(self, text: str) -> list[float]:
        """Эмбеддинг запроса через тёплый bge-m3 (размерность 1024, как в Qdrant)."""
        from app.tools.embedder import embed

        return embed(text)

