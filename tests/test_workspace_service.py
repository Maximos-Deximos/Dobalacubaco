# Testes do serviço de aplicação de workspaces.

import pytest

from app.application.proposal_service import ProposalService
from app.application.workspace_service import WorkspaceService
from app.ingestion.storage import SourceStorage
from app.memory.database import init_db
from app.memory.workspace_repository import WorkspaceNotFoundError


# Cria e lista workspaces pela camada de aplicação.
def test_workspace_service_flow(isolated_database: str) -> None:
    init_db(isolated_database)
    service = WorkspaceService()

    workspace = service.create("Edital de Saúde", "Projeto comunitário")

    assert service.get(workspace.id).name == "Edital de Saúde"
    assert [item.id for item in service.list_all()] == [workspace.id]


# Exclui o workspace, os dados vinculados e os arquivos locais.
def test_workspace_service_deletes_workspace_and_files(
    isolated_database: str,
) -> None:
    init_db(isolated_database)
    service = WorkspaceService()
    workspace = service.create("Edital descartável", "")
    ProposalService().create(workspace.id, "Proposta vinculada")

    source_dir = SourceStorage().source_dir(workspace.id, 1)
    source_dir.mkdir(parents=True)
    (source_dir / "original.pdf").write_bytes(b"%PDF-1.4")

    deleted = service.delete(workspace.id)

    assert deleted.id == workspace.id
    assert service.list_all() == []
    assert ProposalService().list_all() == []
    assert not source_dir.exists()
    with pytest.raises(WorkspaceNotFoundError):
        service.get(workspace.id)
