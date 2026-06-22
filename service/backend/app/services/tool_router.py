from app.schemas.query import ParsedQuery, StructuredResult, ToolName
from app.tools.postgres_tool import PostgresTool
from app.tools.qdrant_tool import QdrantTool


class ToolRouter:
    """Вызывает нужные инструменты по списку query.tools."""

    def __init__(self) -> None:
        self.postgres = PostgresTool()
        self.qdrant = QdrantTool()

    def run(self, query: ParsedQuery) -> StructuredResult:
        merged = StructuredResult(parsed_query=query)

        if ToolName.POSTGRES in query.tools:
            self._merge(merged, self.postgres.run(query))

        if ToolName.QDRANT in query.tools:
            self._merge(merged, self.qdrant.run(query))

        if not query.tools:
            merged.warnings.append("В ParsedQuery не указан ни один инструмент.")

        return merged

    def _merge(self, target: StructuredResult, source: StructuredResult) -> None:
        target.metrics.extend(source.metrics)
        target.rows.extend(source.rows)
        target.examples.extend(source.examples)
        target.warnings.extend(source.warnings)
        target.raw.update(source.raw)
