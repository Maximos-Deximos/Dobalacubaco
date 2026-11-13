# Casos de uso do chat local com recuperação de fontes.

from __future__ import annotations

from app.ai.ollama_client import OllamaClient
from app.ai.promts import INSUFFICIENT_EVIDENCE, build_chat_messages
from app.ai.response_parser import parse_chat_answer
from app.config import Settings, get_settings
from app.memory.chunk_repository import ChunkRepository
from app.memory.source_repository import SourceRepository
from app.memory.workspace_repository import WorkspaceRepository
from app.rag.retriever import Retriever
from app.schemas.rag import ChatAnswer, ChatMessage, ChatStatus
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
        client: OllamaClient | None = None,
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
        self.client = client or OllamaClient(
            host=self.settings.ollama_host,
            timeout=self.settings.ollama_timeout,
        )
        self.retriever = retriever or Retriever(
            settings=self.settings,
            chunk_repository=self.chunk_repository,
            embedder=self.client,
        )

    # Responde uma pergunta usando apenas os trechos indexados do workspace.
    def ask(
        self,
        workspace_id: int,
        question: str,
        *,
        top_k: int | None = None,
        history: list[ChatMessage] | None = None,
    ) -> ChatAnswer:
        if not question.strip():
            raise ChatServiceError("A pergunta não pode estar vazia.")

        self.workspace_repository.get(workspace_id)
        retrieval = self.retriever.retrieve(
            workspace_id,
            question,
            top_k=top_k,
        )

        if not retrieval.hits:
            return ChatAnswer(
                answer=INSUFFICIENT_EVIDENCE,
                mode=retrieval.mode,
                model=self.settings.ollama_model,
                retrieved_count=0,
                warnings=retrieval.warnings,
            )

        trimmed_history = self._trim_history(history)
        messages = build_chat_messages(
            question,
            retrieval.hits,
            max_context_chars=self.settings.rag_max_context_chars,
            history=trimmed_history,
        )
        raw_answer = self.client.chat(
            self.settings.ollama_model,
            messages,
            temperature=self.settings.rag_temperature,
        )
        return parse_chat_answer(
            raw_answer,
            retrieval.hits,
            model=self.settings.ollama_model,
            mode=retrieval.mode,
            warnings=retrieval.warnings,
        )

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
            embedding_model=self.settings.ollama_embed_model,
        )

    # Limita o histórico enviado ao modelo.
    def _trim_history(
        self,
        history: list[ChatMessage] | None,
    ) -> list[ChatMessage] | None:
        if not history or self.settings.rag_history_turns <= 0:
            return None
        return history[-self.settings.rag_history_turns * 2 :]
