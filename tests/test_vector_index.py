# Testes do índice vetorial em memória e do cache.

from dataclasses import dataclass

from app.rag.vector_index import VectorIndex, VectorIndexCache


@dataclass
class Item:
    name: str
    embedding: list[float] | None


# Busca por similaridade e respeita o limite mínimo.
def test_search_returns_best_matches() -> None:
    index = VectorIndex.build(
        [
            Item("nome", [1.0, 0.0]),
            Item("email", [0.0, 1.0]),
            Item("sem vetor", None),
        ],
        lambda item: item.embedding,
    )

    matches = index.search([1.0, 0.0], top_k=2, min_score=-1.0)

    assert [match.item.name for match in matches] == ["nome", "email"]
    assert matches[0].score == 1.0
    assert [match.item.name for match in index.search([1.0, 0.0])] == ["nome"]
    assert index.search([1.0, 0.0], min_score=0.99)[0].item.name == "nome"
    assert index.search([1.0, 0.0], min_score=1.0) == []


# Busca em lote preserva a ordem das consultas.
def test_search_many_preserves_query_order() -> None:
    index = VectorIndex.build(
        [Item("nome", [1.0, 0.0]), Item("email", [0.0, 1.0])],
        lambda item: item.embedding,
    )

    results = index.search_many([[0.0, 1.0], [1.0, 0.0]], top_k=1)

    assert results[0][0].item.name == "email"
    assert results[1][0].item.name == "nome"


# Ignora vetores de dimensões incompatíveis e consultas inválidas.
def test_handles_invalid_dimensions() -> None:
    index = VectorIndex.build(
        [
            Item("a", [1.0, 0.0]),
            Item("b", [1.0, 0.0, 0.0]),
            Item("zero", [0.0, 0.0]),
        ],
        lambda item: item.embedding,
    )

    assert [item.name for item in index.items] == ["a"]
    assert index.search([1.0]) == []
    assert index.search_many([[]]) == [[]]
    assert index.search([1.0, 0.0], top_k=0) == []


# Invalida entradas por chave ou prefixo.
def test_cache_invalidation() -> None:
    cache: VectorIndexCache[Item] = VectorIndexCache()
    built = VectorIndex.build([Item("a", [1.0])], lambda item: item.embedding)

    assert cache.get((1, "fake"), lambda: built) is built
    cache.invalidate_prefix(1)
    assert cache.get((1, "fake"), lambda: VectorIndex.build([], lambda item: item)) is not built
    cache.get((2, "fake"), lambda: built)
    cache.invalidate()
    assert cache.get((2, "fake"), lambda: built) is built
