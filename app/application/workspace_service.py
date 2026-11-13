# Casos de uso relacionados a workspaces de editais.

from __future__ import annotations

from app.memory.workspace_repository import WorkspaceRepository
from app.schemas.workspace import Workspace, WorkspaceCreate


# Serviço de aplicação para criação e consulta de workspaces.
class WorkspaceService:
    def __init__(self, repository: WorkspaceRepository | None = None) -> None:
        self.repository = repository or WorkspaceRepository()

    def create(
        self,
        name: str,
        description: str = "",
    ) -> Workspace:
        data = WorkspaceCreate(name=name, description=description)
        return self.repository.create(data)

    def list_all(self) -> list[Workspace]:
        return self.repository.list_all()

    def get(self, workspace_id: int) -> Workspace:
        return self.repository.get(workspace_id)
