# Testes da recuperação semântica e lexical de trechos.


import pytest

from app.ai.ollama_client import OllamaError
from app.application.workspace_service import WorkspaceService
from app.memory.chunk_repository import ChunkRepository
from app.memory.database import init_db
from app.memory.source_repository import SourceRepository
from app.rag.retriever import Retriever
from app.schemas.rag import ChunkDraft, RetrievalMode
from app.schemas.source import SourceKind, SourceStatus


# Embedder falso que devolve um vetor fixo ou falha.
class FakeEmbedder:
    def __init__(self, vector: list[float] | None = None, fail: bool = False) -> None:
        self.vector = vector or [1.0, 0.0]
        self.fail = fail

    def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        if self.fail:
            raise OllamaError("embedding indisponível")
        return [self.vector for _ in texts]


# Cria workspace, fonte e trechos com embeddings conhecidos.
def make_indexed_workspace(
    workspace_name: str = "Workspace",
    chunks: list[tuple[str, list[float]]] | None = None,
) -> tuple[int, int]:
    workspace = WorkspaceService().create(workspace_name)
    source = SourceRepository().create(
        workspace_id=workspace.id,
        source_kind=SourceKind.UPLOADED_PDF,
        title="Edital de Teste",
        status=SourceStatus.READY,
    )
    drafts = [
        ChunkDraft(
            chunk_index=index,
            text=text,
            char_start=0,
            char_end=len(text),
            page_number=index + 1,
            section_title="",
            chunk_hash=f"hash-{index}",
        )
        for index, (text, _embedding) in enumerate(chunks or [])
    ]
    embeddings = [embedding for _text, embedding in (chunks or [])]
    ChunkRepository().create_many(
        workspace_id=workspace.id,
        source_id=source.id,
        drafts=drafts,
        embeddings=embeddings or None,
        embedding_model="bge-m3" if embeddings else None,
    )
    return workspace.id, source.id


# Recupera primeiro o trecho com maior similaridade.
def test_semantic_ranking(isolated_database) -> None:
    init_db()
    workspace_id, _source_id = make_indexed_workspace(
        chunks=[
            ("prazo de submissão", [1.0, 0.0]),
            ("orçamento previsto", [0.0, 1.0]),
        ]
    )
    retriever = Retriever(embedder=FakeEmbedder([1.0, 0.0]))

    result = retriever.retrieve(workspace_id, "qual o prazo?", top_k=2)

    assert result.mode == RetrievalMode.SEMANTIC
    assert result.hits
    assert result.hits[0].chunk.text == "prazo de submissão"
    assert result.hits[0].score > 0


# Usa busca lexical quando o embedding falha.
def test_falls_back_to_lexical_on_embedding_error(isolated_database) -> None:
    init_db()
    workspace_id, _source_id = make_indexed_workspace(
        chunks=[("o prazo de submissão é trinta dias", [1.0, 0.0])]
    )
    retriever = Retriever(embedder=FakeEmbedder(fail=True))

    result = retriever.retrieve(workspace_id, "prazo")

    assert result.mode == RetrievalMode.LEXICAL
    assert result.hits
    assert "prazo" in result.hits[0].chunk.text
    assert any("lexical" in warning for warning in result.warnings)


# Usa busca lexical quando não existem embeddings.
def test_falls_back_to_lexical_without_embeddings(isolated_database) -> None:
    init_db()
    workspace_id, _source_id = make_indexed_workspace(
        chunks=[("requisitos técnicos obrigatórios", [])]
    )
    retriever = Retriever(embedder=FakeEmbedder())

    result = retriever.retrieve(workspace_id, "requisitos")

    assert result.mode == RetrievalMode.LEXICAL
    assert result.hits


# Respeita o limite de trechos.
def test_top_k_limit(isolated_database) -> None:
    init_db()
    workspace_id, _source_id = make_indexed_workspace(
        chunks=[
            ("primeiro requisito", [1.0, 0.0]),
            ("segundo requisito", [1.0, 0.0]),
            ("terceiro requisito", [1.0, 0.0]),
        ]
    )
    retriever = Retriever(embedder=FakeEmbedder([1.0, 0.0]))

    result = retriever.retrieve(workspace_id, "requisito", top_k=2)

    assert len(result.hits) == 2


# Não mistura trechos de workspaces diferentes.
def test_workspace_isolation(isolated_database) -> None:
    init_db()
    workspace_one, _source_one = make_indexed_workspace(
        "Workspace Um",
        [("requisito do primeiro", [1.0, 0.0])],
    )
    workspace_two, _source_two = make_indexed_workspace(
        "Workspace Dois",
        [("requisito do segundo", [1.0, 0.0])],
    )
    retriever = Retriever(embedder=FakeEmbedder([1.0, 0.0]))

    result = retriever.retrieve(workspace_two, "requisito", top_k=5)

    assert result.hits
    assert all(
        hit.chunk.workspace_id == workspace_two for hit in result.hits
    )
    assert workspace_one != workspace_two


# Rejeita pergunta vazia.
def test_empty_query(isolated_database) -> None:
    init_db()
    workspace_id, _source_id = make_indexed_workspace()

    with pytest.raises(ValueError):
        Retriever(embedder=FakeEmbedder()).retrieve(workspace_id, "  ")
