# Testes da indexação de fontes para busca e chat.

from dataclasses import replace

import pytest

from app.ai.ollama_client import OllamaError
from app.application.indexing_service import IndexingError, IndexingService
from app.application.workspace_service import WorkspaceService
from app.config import get_settings
from app.memory.chunk_repository import ChunkRepository
from app.memory.database import init_db
from app.memory.source_repository import SourceRepository
from app.schemas.source import ExtractedSegment, SourceKind, SourceStatus


# Embedder falso com vetores previsíveis.
class FakeEmbedder:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[list[str]] = []

    def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        if self.fail:
            raise OllamaError("modelo de embedding indisponível")
        return [[1.0, float(len(text) % 7)] for text in texts]


# Cria um workspace com uma fonte pronta e snapshot.
def make_source(workspace_name: str = "Workspace") -> tuple[int, int]:
    workspace = WorkspaceService().create(workspace_name)
    repository = SourceRepository()
    source = repository.create(
        workspace_id=workspace.id,
        source_kind=SourceKind.UPLOADED_PDF,
        title="Edital de Teste",
        status=SourceStatus.READY,
    )
    text = "Requisitos do edital. Prazo de submissão. Orçamento previsto."
    repository.save_snapshot(
        source.id,
        raw_path="/tmp/source.pdf",
        content_text=text,
        segments=[
            ExtractedSegment(
                kind="page",
                index=1,
                title="Página 1",
                text=text,
                start_offset=0,
                end_offset=len(text),
            ).model_dump(mode="json")
        ],
        metadata={"title": "Edital de Teste"},
        warnings=[],
        page_count=1,
        http_status=200,
    )
    return workspace.id, source.id


# Indexa os trechos e gera embeddings.
def test_index_creates_chunks_and_embeddings(isolated_database) -> None:
    init_db()
    workspace_id, source_id = make_source()
    embedder = FakeEmbedder()

    result = IndexingService(embedder=embedder).index_workspace(workspace_id)

    assert result.sources_indexed == 1
    assert result.chunks_created == 1
    assert result.embeddings_created == 1
    assert result.embedding_model == "bge-m3"
    chunks = ChunkRepository().list_by_source(source_id)
    assert chunks[0].embedding is not None
    assert chunks[0].embedding_model == "bge-m3"


# Uma segunda indexação sem mudanças não recria os trechos.
def test_index_is_idempotent(isolated_database) -> None:
    init_db()
    workspace_id, source_id = make_source()
    service = IndexingService(embedder=FakeEmbedder())

    first = service.index_workspace(workspace_id)
    second = service.index_workspace(workspace_id)

    assert first.chunks_created == 1
    assert second.sources_skipped == 1
    assert second.chunks_created == 0
    assert len(ChunkRepository().list_by_source(source_id)) == 1


# --force recria os trechos mesmo já indexados.
def test_force_reindex(isolated_database) -> None:
    init_db()
    workspace_id, _source_id = make_source()
    service = IndexingService(embedder=FakeEmbedder())
    service.index_workspace(workspace_id)

    result = service.index_workspace(workspace_id, force=True)

    assert result.sources_indexed == 1
    assert result.chunks_created == 1


# Falha de embedding mantém o índice lexical utilizável.
def test_embedding_failure_keeps_lexical_chunks(isolated_database) -> None:
    init_db()
    workspace_id, source_id = make_source()
    service = IndexingService(embedder=FakeEmbedder(fail=True))

    result = service.index_workspace(workspace_id)

    assert result.sources_indexed == 1
    assert result.chunks_created == 1
    assert result.embeddings_created == 0
    assert result.warnings
    chunk = ChunkRepository().list_by_source(source_id)[0]
    assert chunk.embedding is None
    assert ChunkRepository().search_lexical(workspace_id, "prazo", 5)


# Fontes sem OCR são ignoradas.
def test_skips_needs_ocr_source(isolated_database) -> None:
    init_db()
    workspace = WorkspaceService().create("Workspace OCR")
    SourceRepository().create(
        workspace_id=workspace.id,
        source_kind=SourceKind.UPLOADED_PDF,
        title="Escaneado",
        status=SourceStatus.NEEDS_OCR,
    )

    result = IndexingService(embedder=FakeEmbedder()).index_workspace(workspace.id)

    assert result.sources_indexed == 0
    assert result.sources_skipped == 1
    assert result.warnings


# Impede indexar uma fonte de outro workspace.
def test_rejects_source_from_other_workspace(isolated_database) -> None:
    init_db()
    workspace_one, _source_one = make_source("Workspace Um")
    _workspace_two, source_two = make_source("Workspace Dois")

    with pytest.raises(IndexingError):
        IndexingService(embedder=FakeEmbedder()).index_workspace(
            workspace_one,
            source_id=source_two,
        )


# Troca de modelo de embedding força a reindexação.
def test_model_change_reindexes(isolated_database) -> None:
    init_db()
    workspace_id, _source_id = make_source()
    IndexingService(embedder=FakeEmbedder()).index_workspace(workspace_id)
    settings = replace(get_settings(), ai_embed_model="outro-modelo")

    result = IndexingService(
        settings=settings,
        embedder=FakeEmbedder(),
    ).index_workspace(workspace_id)

    assert result.sources_indexed == 1
    assert result.chunks_created == 1
