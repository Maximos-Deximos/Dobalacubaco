# Testes do repositório de trechos e da busca lexical FTS5.

from app.application.workspace_service import WorkspaceService
from app.memory.chunk_repository import ChunkRepository
from app.memory.database import init_db
from app.memory.source_repository import SourceRepository
from app.schemas.rag import ChunkDraft
from app.schemas.source import SourceKind


# Cria um workspace e uma fonte para os testes de trechos.
def make_source(workspace_name: str = "Workspace") -> tuple[int, int]:
    workspace = WorkspaceService().create(workspace_name)
    source = SourceRepository().create(
        workspace_id=workspace.id,
        source_kind=SourceKind.UPLOADED_PDF,
        title="Edital",
    )
    return workspace.id, source.id


# Monta um trecho de teste.
def make_draft(index: int, text: str) -> ChunkDraft:
    return ChunkDraft(
        chunk_index=index,
        text=text,
        char_start=index * 10,
        char_end=index * 10 + len(text),
        page_number=index + 1,
        section_title="Requisitos",
        chunk_hash=f"hash-{index}",
    )


# Persiste e lista trechos com embeddings.
def test_create_and_list_chunks(isolated_database) -> None:
    init_db()
    workspace_id, source_id = make_source()
    repository = ChunkRepository()

    chunks = repository.create_many(
        workspace_id=workspace_id,
        source_id=source_id,
        drafts=[make_draft(0, "Primeiro trecho"), make_draft(1, "Segundo trecho")],
        embeddings=[[0.1, 0.2], [0.3, 0.4]],
        embedding_model="bge-m3",
    )

    assert [chunk.chunk_index for chunk in chunks] == [0, 1]
    assert chunks[0].embedding_dim == 2
    assert chunks[0].embedding_model == "bge-m3"
    assert chunks[0].embedding == [0.1, 0.2]
    assert len(repository.list_by_source(source_id)) == 2


# Busca lexical ignora acentos e encontra o termo no workspace.
def test_lexical_search_removes_diacritics(isolated_database) -> None:
    init_db()
    workspace_id, source_id = make_source()
    repository = ChunkRepository()
    repository.create_many(
        workspace_id=workspace_id,
        source_id=source_id,
        drafts=[
            make_draft(0, "O edital exige inovação e requisitos técnicos."),
            make_draft(1, "O prazo de submissão é de trinta dias."),
        ],
    )

    results = repository.search_lexical(workspace_id, "inovacao", 5)

    assert results
    assert results[0].chunk.source_id == source_id
    assert "inovação" in results[0].chunk.text
    assert results[0].score > 0


# A busca lexical respeita o isolamento entre workspaces.
def test_lexical_search_is_workspace_scoped(isolated_database) -> None:
    init_db()
    workspace_one, source_one = make_source("Workspace Um")
    workspace_two, source_two = make_source("Workspace Dois")
    repository = ChunkRepository()
    repository.create_many(
        workspace_id=workspace_one,
        source_id=source_one,
        drafts=[make_draft(0, "requisito exclusivo do primeiro")],
    )
    repository.create_many(
        workspace_id=workspace_two,
        source_id=source_two,
        drafts=[make_draft(0, "requisito exclusivo do segundo")],
    )

    results = repository.search_lexical(workspace_two, "requisito", 5)

    assert len(results) == 1
    assert results[0].chunk.workspace_id == workspace_two


# Remover a fonte também remove os trechos do índice lexical.
def test_delete_by_source_removes_fts_rows(isolated_database) -> None:
    init_db()
    workspace_id, source_id = make_source()
    repository = ChunkRepository()
    repository.create_many(
        workspace_id=workspace_id,
        source_id=source_id,
        drafts=[make_draft(0, "conteúdo removível")],
    )

    assert repository.delete_by_source(source_id) == 1
    assert repository.search_lexical(workspace_id, "removivel", 5) == []


# Conta trechos totais e com embeddings.
def test_count_by_workspace(isolated_database) -> None:
    init_db()
    workspace_id, source_id = make_source()
    repository = ChunkRepository()
    repository.create_many(
        workspace_id=workspace_id,
        source_id=source_id,
        drafts=[make_draft(0, "sem embedding")],
    )

    assert repository.count_by_workspace(workspace_id) == (1, 0)
