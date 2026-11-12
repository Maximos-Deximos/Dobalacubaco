# Testes do serviço de aplicação de workspaces.

from app.application.workspace_service import WorkspaceService
from app.memory.database import init_db


# Cria e lista workspaces pela camada de aplicação.
def test_workspace_service_flow(isolated_database: str) -> None:
    init_db(isolated_database)
    service = WorkspaceService()

    workspace = service.create("Edital de Saúde", "Projeto comunitário")

    assert service.get(workspace.id).name == "Edital de Saúde"
    assert [item.id for item in service.list_all()] == [workspace.id]
