# Testes do repositório de workspaces.

import pytest

from app.memory.database import init_db
from app.memory.workspace_repository import (
    WorkspaceAlreadyExistsError,
    WorkspaceNotFoundError,
    WorkspaceRepository,
)
from app.schemas.workspace import WorkspaceCreate


# Prepara o banco e devolve um repositório pronto para uso.
@pytest.fixture
def repository(isolated_database: str) -> WorkspaceRepository:
    init_db(isolated_database)
    return WorkspaceRepository(isolated_database)


# Cria e recupera um workspace pelo ID.
def test_create_and_get_workspace(repository: WorkspaceRepository) -> None:
    created = repository.create(
        WorkspaceCreate(name="Edital de Inovação", description="Projeto teste")
    )

    loaded = repository.get(created.id)

    assert loaded.name == "Edital de Inovação"
    assert loaded.description == "Projeto teste"
    assert loaded.status.value == "active"


# Impede nomes duplicados.
def test_rejects_duplicate_name(repository: WorkspaceRepository) -> None:
    repository.create(WorkspaceCreate(name="Duplicado"))

    with pytest.raises(WorkspaceAlreadyExistsError):
        repository.create(WorkspaceCreate(name="Duplicado"))


# Lista em ordem de criação.
def test_list_all(repository: WorkspaceRepository) -> None:
    first = repository.create(WorkspaceCreate(name="Primeiro"))
    second = repository.create(WorkspaceCreate(name="Segundo"))

    workspaces = repository.list_all()

    assert [workspace.id for workspace in workspaces] == [first.id, second.id]


# Informa quando o workspace não existe.
def test_missing_workspace_raises(repository: WorkspaceRepository) -> None:
    with pytest.raises(WorkspaceNotFoundError):
        repository.get(999)
