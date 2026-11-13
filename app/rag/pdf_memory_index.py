# Índice vetorial em memória para valores de campos revisados.

from __future__ import annotations

import numpy as np

from app.config import Settings, get_settings
from app.memory.pdf_form_repository import PdfMemoryRepository
from app.rag.vector_index import VectorIndex, VectorIndexCache, VectorMatch
from app.schemas.pdf import PdfFieldMemory


# Mantém um índice de memórias por workspace e modelo de embedding.
class PdfMemoryIndex:
    def __init__(
        self,
        settings: Settings | None = None,
        repository: PdfMemoryRepository | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.repository = repository or PdfMemoryRepository(
            self.settings.database_url
        )
        self._cache: VectorIndexCache[PdfFieldMemory] = VectorIndexCache()

    # Busca exemplos semelhantes para cada vetor de consulta.
    def similar_many(
        self,
        workspace_id: int,
        query_embeddings: list[list[float]],
        *,
        embedding_model: str,
        top_k: int = 3,
        min_score: float = 0.82,
    ) -> list[list[VectorMatch[PdfFieldMemory]]]:
        if not query_embeddings:
            return []
        index = self._index(workspace_id, embedding_model)
        return index.search_many(
            query_embeddings,
            top_k=top_k,
            min_score=min_score,
        )

    # Invalida o cache após gravar novas memórias.
    def invalidate(self, workspace_id: int) -> None:
        self._cache.invalidate_prefix(workspace_id)

    # Monta ou reutiliza o índice do workspace.
    def _index(self, workspace_id: int, embedding_model: str) -> VectorIndex[PdfFieldMemory]:
        key = (workspace_id, embedding_model)

        def build() -> VectorIndex[PdfFieldMemory]:
            memories = self.repository.list_by_workspace(
                workspace_id,
                only_embedded=True,
                embedding_model=embedding_model,
            )
            return VectorIndex.build(memories, lambda item: item.embedding)

        return self._cache.get(key, build)


# Gera embeddings normalizados para consultas vetoriais.
def normalize_embedding(embedding: list[float] | None) -> list[float]:
    if not embedding:
        return []
    vector = np.asarray(embedding, dtype=np.float32)
    norm = float(np.linalg.norm(vector))
    if norm <= 0:
        return []
    return (vector / norm).tolist()
