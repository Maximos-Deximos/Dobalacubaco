# Repositório responsável pela conversa persistida de cada workspace.

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, select

from app.memory.database import session_scope
from app.memory.models import ChatMessageModel
from app.schemas.rag import ChatMessageRecord


# Converte o modelo ORM no contrato Pydantic usado pela aplicação.
def _to_schema(model: ChatMessageModel) -> ChatMessageRecord:
    return ChatMessageRecord.model_validate(model)


# Repositório de mensagens do chat local.
class ChatRepository:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url

    # Grava a pergunta e a resposta na mesma transação.
    def append_exchange(
        self,
        workspace_id: int,
        *,
        question: str,
        answer: str,
        answer_metadata: dict[str, Any] | None = None,
    ) -> list[ChatMessageRecord]:
        with session_scope(self.database_url) as session:
            models = [
                ChatMessageModel(
                    workspace_id=workspace_id,
                    role="user",
                    content=question,
                    extra_metadata={},
                ),
                ChatMessageModel(
                    workspace_id=workspace_id,
                    role="assistant",
                    content=answer,
                    extra_metadata=answer_metadata or {},
                ),
            ]
            session.add_all(models)
            session.flush()
            return [_to_schema(model) for model in models]

    # Lista a conversa em ordem cronológica, opcionalmente só as últimas N.
    def list_by_workspace(
        self,
        workspace_id: int,
        *,
        limit: int | None = None,
    ) -> list[ChatMessageRecord]:
        with session_scope(self.database_url) as session:
            statement = (
                select(ChatMessageModel)
                .where(ChatMessageModel.workspace_id == workspace_id)
                .order_by(ChatMessageModel.id.desc())
            )
            if limit is not None:
                statement = statement.limit(limit)

            models = list(session.scalars(statement).all())
            models.reverse()
            return [_to_schema(model) for model in models]

    # Conta as mensagens persistidas de um workspace.
    def count_by_workspace(self, workspace_id: int) -> int:
        with session_scope(self.database_url) as session:
            total = session.scalar(
                select(func.count(ChatMessageModel.id)).where(
                    ChatMessageModel.workspace_id == workspace_id
                )
            )
            return int(total or 0)

    # Remove toda a conversa de um workspace e devolve a quantidade apagada.
    def clear(self, workspace_id: int) -> int:
        with session_scope(self.database_url) as session:
            result = session.execute(
                delete(ChatMessageModel).where(
                    ChatMessageModel.workspace_id == workspace_id
                )
            )
            return int(result.rowcount or 0)
