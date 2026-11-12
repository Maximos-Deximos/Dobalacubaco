# Repositório responsável pela leitura e escrita de workspaces.

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.memory.database import session_scope
from app.memory.models import WorkspaceModel
from app.schemas.workspace import Workspace, WorkspaceCreate


# Erro lançado quando o workspace solicitado não existe.
class WorkspaceNotFoundError(LookupError):
    pass


# Erro lançado quando já existe um workspace com o mesmo nome.
class WorkspaceAlreadyExistsError(ValueError):
    pass


# Converte o modelo ORM no contrato Pydantic usado pela aplicação.
def _to_schema(model: WorkspaceModel) -> Workspace:
    return Workspace.model_validate(model)


# Repositório de workspaces locais.
class WorkspaceRepository:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url

    # Cria um workspace com nome único.
    def create(self, data: WorkspaceCreate) -> Workspace:
        with session_scope(self.database_url) as session:
            existing = session.scalar(
                select(WorkspaceModel).where(WorkspaceModel.name == data.name)
            )
            if existing is not None:
                raise WorkspaceAlreadyExistsError(
                    f"Já existe uma área de trabalho chamada '{data.name}'."
                )

            model = WorkspaceModel(**data.model_dump(mode="json"))
            session.add(model)
            try:
                session.flush()
            except IntegrityError as exc:
                raise WorkspaceAlreadyExistsError(
                    f"Já existe uma área de trabalho chamada '{data.name}'."
                ) from exc
            return _to_schema(model)

    # Busca um workspace pelo identificador.
    def get(self, workspace_id: int) -> Workspace:
        with session_scope(self.database_url) as session:
            model = session.get(WorkspaceModel, workspace_id)
            if model is None:
                raise WorkspaceNotFoundError(
                    f"Área de trabalho {workspace_id} não encontrada."
                )
            return _to_schema(model)

    # Busca um workspace pelo nome.
    def get_by_name(self, name: str) -> Workspace | None:
        with session_scope(self.database_url) as session:
            model = session.scalar(
                select(WorkspaceModel).where(WorkspaceModel.name == name)
            )
            return _to_schema(model) if model is not None else None

    # Lista todos os workspaces em ordem de criação.
    def list_all(self) -> list[Workspace]:
        with session_scope(self.database_url) as session:
            models = session.scalars(
                select(WorkspaceModel).order_by(WorkspaceModel.id)
            ).all()
            return [_to_schema(model) for model in models]
