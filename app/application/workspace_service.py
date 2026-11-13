# Casos de uso relacionados a workspaces de editais.

from __future__ import annotations

from app.ingestion.storage import SourceStorage
from app.memory.workspace_repository import WorkspaceRepository
from app.schemas.workspace import Workspace, WorkspaceCreate


# Serviço de aplicação para criação, consulta e exclusão de workspaces.
class WorkspaceService:
    def __init__(
        self,
        repository: WorkspaceRepository | None = None,
        storage: SourceStorage | None = None,
    ) -> None:
        self.repository = repository or WorkspaceRepository()
        self.storage = storage or SourceStorage()

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

    def delete(self, workspace_id: int) -> Workspace:
        workspace = self.repository.delete(workspace_id)
        self.storage.delete_workspace(workspace_id)
        return workspace
