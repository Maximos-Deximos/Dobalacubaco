# Índice vetorial simples em memória usando similaridade de cosseno.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

import numpy as np

T = TypeVar("T")


# Correspondência individual de uma busca vetorial.
@dataclass(slots=True)
class VectorMatch(Generic[T]):
    item: T
    score: float
    index: int


# Matriz de vetores com busca em lote.
@dataclass(slots=True)
class VectorIndex(Generic[T]):
    items: list[T] = field(default_factory=list)
    vectors: np.ndarray | None = None

    # Monta a matriz normalizada a partir de itens com embedding.
    @classmethod
    def build(
        cls,
        items: list[T],
        embedding_getter,
    ) -> VectorIndex[T]:
        valid: list[T] = []
        rows: list[list[float]] = []
        dimension: int | None = None

        for item in items:
            embedding = embedding_getter(item)
            if not embedding:
                continue
            vector = np.asarray(embedding, dtype=np.float32)
            if vector.ndim != 1 or vector.size == 0:
                continue
            if dimension is None:
                dimension = int(vector.size)
            if vector.size != dimension:
                continue
            norm = float(np.linalg.norm(vector))
            if norm <= 0:
                continue
            valid.append(item)
            rows.append((vector / norm).tolist())

        if not valid:
            return cls(items=[], vectors=None)
        return cls(items=valid, vectors=np.asarray(rows, dtype=np.float32))

    # Indica se o índice possui vetores utilizáveis.
    def is_empty(self) -> bool:
        return self.vectors is None or self.vectors.size == 0

    # Busca os itens mais similares para um vetor.
    def search(
        self,
        query: list[float],
        *,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> list[VectorMatch[T]]:
        if not query:
            return []
        return self.search_many(
            [query],
            top_k=top_k,
            min_score=min_score,
        )[0]

    # Busca em lote, reaproveitando a mesma matriz.
    def search_many(
        self,
        queries: list[list[float]],
        *,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> list[list[VectorMatch[T]]]:
        if self.is_empty() or not queries:
            return [[] for _ in queries]

        assert self.vectors is not None
        if top_k < 1:
            return [[] for _ in queries]

        query_rows: list[np.ndarray] = []
        for query in queries:
            if not query:
                query_rows.append(np.zeros(self.vectors.shape[1], dtype=np.float32))
                continue
            vector = np.asarray(query, dtype=np.float32)
            if vector.ndim != 1 or vector.size != self.vectors.shape[1]:
                query_rows.append(np.zeros(self.vectors.shape[1], dtype=np.float32))
                continue
            norm = float(np.linalg.norm(vector))
            query_rows.append(
                vector / norm if norm > 0 else np.zeros_like(vector)
            )

        query_matrix = np.vstack(query_rows)
        scores = query_matrix @ self.vectors.T
        results: list[list[VectorMatch[T]]] = []

        for row in scores:
            order = np.argsort(-row)[:top_k]
            matches: list[VectorMatch[T]] = []
            for index in order:
                score = float(row[int(index)])
                if score <= min_score:
                    continue
                matches.append(
                    VectorMatch(
                        item=self.items[int(index)],
                        score=score,
                        index=int(index),
                    )
                )
            results.append(matches)
        return results


# Cache simples de índices vetoriais por chave arbitrária.
class VectorIndexCache(Generic[T]):
    def __init__(self) -> None:
        self._cache: dict[Any, VectorIndex[T]] = {}

    # Devolve do cache ou monta com a função informada.
    def get(self, key: Any, builder) -> VectorIndex[T]:
        index = self._cache.get(key)
        if index is None:
            index = builder()
            self._cache[key] = index
        return index

    # Remove uma entrada ou limpa o cache inteiro.
    def invalidate(self, key: Any | None = None) -> None:
        if key is None:
            self._cache.clear()
        else:
            self._cache.pop(key, None)

    # Remove todas as entradas cujo primeiro item da chave coincide.
    def invalidate_prefix(self, key_prefix: Any) -> None:
        for key in list(self._cache):
            if isinstance(key, tuple) and key and key[0] == key_prefix:
                self._cache.pop(key, None)
