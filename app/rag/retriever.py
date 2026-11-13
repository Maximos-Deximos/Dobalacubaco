# Recuperação semântica e lexical de trechos de editais.

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.ai.ollama_client import OllamaClient, OllamaError
from app.config import Settings, get_settings
from app.memory.chunk_repository import ChunkRepository
from app.schemas.rag import RetrievalHit, RetrievalMode


# Resultado da recuperação com o modo efetivamente usado.
@dataclass(slots=True)
class RetrievalResult:
    hits: list[RetrievalHit] = field(default_factory=list)
    mode: RetrievalMode = RetrievalMode.LEXICAL
    warnings: list[str] = field(default_factory=list)


# Recupera trechos relevantes para uma pergunta.
class Retriever:
    def __init__(
        self,
        settings: Settings | None = None,
        chunk_repository: ChunkRepository | None = None,
        embedder: OllamaClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.chunk_repository = chunk_repository or ChunkRepository(
            self.settings.database_url
        )
        self.embedder = embedder

    # Busca primeiro por similaridade semântica e recorre ao FTS5 se necessário.
    def retrieve(
        self,
        workspace_id: int,
        query: str,
        *,
        top_k: int | None = None,
    ) -> RetrievalResult:
        if not query.strip():
            raise ValueError("A pergunta não pode estar vazia.")

        limit = top_k if top_k is not None else self.settings.rag_top_k
        if limit < 1:
            raise ValueError("A quantidade de trechos deve ser pelo menos 1.")

        warnings: list[str] = []
        if self.embedder is not None and self.settings.ollama_embed_model:
            semantic = self._semantic_search(
                workspace_id,
                query,
                limit,
                warnings,
            )
            if semantic:
                return RetrievalResult(
                    hits=semantic,
                    mode=RetrievalMode.SEMANTIC,
                    warnings=warnings,
                )

        lexical = self._lexical_search(workspace_id, query, limit, warnings)
        return RetrievalResult(
            hits=lexical,
            mode=RetrievalMode.LEXICAL,
            warnings=warnings,
        )

    # Calcula similaridade de cosseno entre a pergunta e os trechos indexados.
    def _semantic_search(
        self,
        workspace_id: int,
        query: str,
        limit: int,
        warnings: list[str],
    ) -> list[RetrievalHit]:
        model = self.settings.ollama_embed_model
        assert self.embedder is not None

        try:
            query_embedding = self.embedder.embed(model, [query])[0]
        except OllamaError as exc:
            warnings.append(
                f"Busca semântica indisponível; usando busca lexical. {exc}"
            )
            return []

        stored = self.chunk_repository.list_by_workspace(
            workspace_id,
            only_embedded=True,
            embedding_model=model,
        )
        if not stored:
            warnings.append(
                "Nenhum trecho possui embeddings; usando busca lexical."
            )
            return []

        vectors = np.asarray(
            [item.chunk.embedding for item in stored],
            dtype=np.float32,
        )
        query_vector = np.asarray(query_embedding, dtype=np.float32)
        if vectors.ndim != 2 or vectors.shape[1] != query_vector.shape[0]:
            warnings.append(
                "Dimensões de embedding incompatíveis; usando busca lexical."
            )
            return []

        dot_products = vectors @ query_vector
        norms = np.linalg.norm(vectors, axis=1) * np.linalg.norm(query_vector)
        scores = np.zeros(len(vectors), dtype=np.float32)
        valid = norms > 0
        scores[valid] = dot_products[valid] / norms[valid]

        order = np.argsort(-scores)[:limit]
        hits: list[RetrievalHit] = []
        for index in order:
            score = float(scores[index])
            if score <= 0:
                continue
            item = stored[int(index)]
            hits.append(
                RetrievalHit(
                    chunk=item.chunk,
                    source_title=item.source_title,
                    source_url=item.source_url,
                    score=score,
                    mode=RetrievalMode.SEMANTIC,
                )
            )

        if not hits:
            warnings.append(
                "Busca semântica não encontrou trechos relevantes; usando busca lexical."
            )
        return hits

    # Busca lexical com FTS5 e BM25.
    def _lexical_search(
        self,
        workspace_id: int,
        query: str,
        limit: int,
        warnings: list[str],
    ) -> list[RetrievalHit]:
        stored = self.chunk_repository.search_lexical(
            workspace_id,
            query,
            limit,
        )
        hits = [
            RetrievalHit(
                chunk=item.chunk,
                source_title=item.source_title,
                source_url=item.source_url,
                score=item.score,
                mode=RetrievalMode.LEXICAL,
            )
            for item in stored
        ]
        if not hits:
            warnings.append("Nenhum trecho relevante foi encontrado no workspace.")
        return hits
