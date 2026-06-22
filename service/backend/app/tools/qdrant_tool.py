from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchAny, MatchValue, Range

from app.core.config import get_settings
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
            qdrant_filter = self._build_filter(query)

            hits = client.search(
                collection_name=self.settings.qdrant_collection,
                query_vector=vector,
                query_filter=qdrant_filter,
                limit=query.limit,
                with_payload=True,
            )
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Ошибка Qdrant-инструмента: {exc}")
            return result

        for hit in hits:
            payload = hit.payload or {}
            result.examples.append(
                ReviewExample(
                    review_id=str(payload.get("review_id") or hit.id),
                    text=str(payload.get("text") or ""),
                    labels=list(payload.get("labels") or []),
                    product_name=payload.get("product_name"),
                    rating=payload.get("rating"),
                    date=str(payload.get("review_date")) if payload.get("review_date") else None,
                    score=float(hit.score) if hit.score is not None else None,
                )
            )

        return result

    def _embed(self, text: str) -> list[float]:
        """Временная точка расширения.

        Заменить на реальный encoder, например bge-m3.
        Важно: размерность должна совпадать с collection в Qdrant.
        """
        raise NotImplementedError("Подключи embedding-модель в QdrantTool._embed().")

    def _build_filter(self, query: ParsedQuery) -> Filter | None:
        conditions = []
        f = query.filters

        if f.labels:
            conditions.append(FieldCondition(key="labels", match=MatchAny(any=f.labels)))
        if f.category:
            conditions.append(FieldCondition(key="category", match=MatchValue(value=f.category)))
        if f.brand:
            conditions.append(FieldCondition(key="brand", match=MatchValue(value=f.brand)))
        if f.product_id:
            conditions.append(FieldCondition(key="product_id", match=MatchValue(value=f.product_id)))
        if f.min_rating is not None or f.max_rating is not None:
            conditions.append(
                FieldCondition(
                    key="rating",
                    range=Range(gte=f.min_rating, lte=f.max_rating),
                )
            )

        if not conditions:
            return None
        return Filter(must=conditions)
