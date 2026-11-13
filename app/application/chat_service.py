# Casos de uso do chat local com recuperação de fontes.

from __future__ import annotations

from app.ai.factory import build_chat_provider, build_embed_provider
from app.ai.promts import (
    NO_INDEXED_SOURCES_WARNING,
    NO_RELEVANT_EXCERPTS_WARNING,
    build_chat_messages,
)
from app.ai.provider import AiProvider
from app.ai.response_parser import parse_chat_answer
from app.config import Settings, get_settings
from app.memory.chat_repository import ChatRepository
from app.memory.chunk_repository import ChunkRepository
from app.memory.source_repository import SourceRepository
from app.memory.workspace_repository import WorkspaceRepository
from app.rag.retriever import Retriever
from app.schemas.rag import (
    ChatAnswer,
    ChatMessage,
    ChatMessageRecord,
    ChatStatus,
)
from app.schemas.source import SourceStatus


# Erro lançado quando o chat não pode ser executado.
class ChatServiceError(RuntimeError):
    pass


# Orquestra recuperação, prompt e resposta do modelo local.
class ChatService:
    def __init__(
        self,
        settings: Settings | None = None,
        workspace_repository: WorkspaceRepository | None = None,
        source_repository: SourceRepository | None = None,
        chunk_repository: ChunkRepository | None = None,
        retriever: Retriever | None = None,
        client: AiProvider | None = None,
        embedder: AiProvider | None = None,
        chat_repository: ChatRepository | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.workspace_repository = workspace_repository or WorkspaceRepository(
            self.settings.database_url
        )
        self.source_repository = source_repository or SourceRepository(
            self.settings.database_url
        )
        self.chunk_repository = chunk_repository or ChunkRepository(
            self.settings.database_url
        )
        self.chat_repository = chat_repository or ChatRepository(
            self.settings.database_url
        )
        self.client = client or build_chat_provider(self.settings)
        self.embedder = embedder or build_embed_provider(self.settings)
        self.retriever = retriever or Retriever(
            settings=self.settings,
            chunk_repository=self.chunk_repository,
            embedder=self.embedder,
        )

    # Responde usando os trechos indexados quando disponíveis, com fallback geral.
    def ask(
        self,
        workspace_id: int,
        question: str,
        *,
        top_k: int | None = None,
        history: list[ChatMessage] | None = None,
        persist: bool = True,
    ) -> ChatAnswer:
        if not question.strip():
            raise ChatServiceError("A pergunta não pode estar vazia.")

        self.workspace_repository.get(workspace_id)
        # Sem histórico explícito, retoma a conversa salva neste workspace.
        if history is None:
            history = self._load_history(workspace_id)

        chunks_total, _embedded = self.chunk_repository.count_by_workspace(
            workspace_id
        )
        hits = []
        warnings: list[str] = []
        mode = None

        if chunks_total:
            retrieval = self.retriever.retrieve(
                workspace_id,
                question,
                top_k=top_k,
            )
            hits = retrieval.hits
            warnings = list(retrieval.warnings)
            mode = retrieval.mode
            if not hits:
                warnings.append(NO_RELEVANT_EXCERPTS_WARNING)
        else:
            warnings.append(NO_INDEXED_SOURCES_WARNING)

        trimmed_history = self._trim_history(history)
        messages = build_chat_messages(
            question,
            hits,
            max_context_chars=self.settings.rag_max_context_chars,
            history=trimmed_history,
        )
        raw_answer = self.client.chat(
            self.settings.ai_model,
            messages,
            temperature=self.settings.rag_temperature,
            max_tokens=self.settings.ai_max_tokens,
        )
        answer = parse_chat_answer(
            raw_answer,
            hits,
            model=self.settings.ai_model,
            mode=mode,
            warnings=warnings,
        )

        if persist:
            try:
                self.chat_repository.append_exchange(
                    workspace_id,
                    question=question.strip(),
                    answer=answer.answer,
                    answer_metadata={"answer": answer.model_dump(mode="json")},
                )
            except Exception as exc:  # noqa: BLE001
                answer.warnings.append(
                    f"Não foi possível salvar a conversa no histórico: {exc}"
                )

        return answer

    # Lista a conversa persistida do workspace em ordem cronológica.
    def conversation(
        self,
        workspace_id: int,
        *,
        limit: int | None = None,
    ) -> list[ChatMessageRecord]:
        self.workspace_repository.get(workspace_id)
        return self.chat_repository.list_by_workspace(workspace_id, limit=limit)

    # Remove a conversa persistida do workspace.
    def clear_conversation(self, workspace_id: int) -> int:
        self.workspace_repository.get(workspace_id)
        return self.chat_repository.clear(workspace_id)

    # Devolve a situação atual da indexação do workspace.
    def status(self, workspace_id: int) -> ChatStatus:
        self.workspace_repository.get(workspace_id)
        sources = self.source_repository.list_by_workspace(workspace_id)
        chunks_total, chunks_embedded = self.chunk_repository.count_by_workspace(
            workspace_id
        )
        return ChatStatus(
            workspace_id=workspace_id,
            sources_total=len(sources),
            sources_ready=sum(
                1 for source in sources if source.status == SourceStatus.READY
            ),
            chunks_total=chunks_total,
            chunks_embedded=chunks_embedded,
            embedding_model=self.settings.ai_embed_model or None,
        )

    # Carrega do banco apenas as mensagens usadas como contexto do modelo.
    def _load_history(self, workspace_id: int) -> list[ChatMessage]:
        limit = self.settings.rag_history_turns * 2
        if limit <= 0:
            return []

        records = self.chat_repository.list_by_workspace(workspace_id, limit=limit)
        return [
            ChatMessage(role=record.role, content=record.content)
            for record in records
        ]

    # Limita o histórico enviado ao modelo.
    def _trim_history(
        self,
        history: list[ChatMessage] | None,
    ) -> list[ChatMessage] | None:
        if not history or self.settings.rag_history_turns <= 0:
            return None
        return history[-self.settings.rag_history_turns * 2 :]
