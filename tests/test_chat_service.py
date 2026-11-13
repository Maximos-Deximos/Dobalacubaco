# Testes do serviço de chat com citações.

from dataclasses import replace

import pytest

from app.ai.promts import (
    NO_INDEXED_SOURCES_WARNING,
    NO_RELEVANT_EXCERPTS_WARNING,
)
from app.application.chat_service import ChatService, ChatServiceError
from app.application.workspace_service import WorkspaceService
from app.config import get_settings
from app.memory.chunk_repository import ChunkRepository
from app.memory.database import init_db
from app.memory.source_repository import SourceRepository
from app.memory.workspace_repository import WorkspaceNotFoundError
from app.rag.retriever import Retriever
from app.schemas.rag import ChatMessage, ChunkDraft, RetrievalMode
from app.schemas.source import SourceKind, SourceStatus


# Cliente falso que registra as mensagens enviadas.
class FakeChatClient:
    def __init__(self, answer: str = "Resposta [F1].") -> None:
        self.answer = answer
        self.messages = []
        self.calls = 0

    def chat(self, model: str, messages, *, temperature: float = 0.1) -> str:
        self.calls += 1
        self.messages = messages
        return self.answer


# Cria um workspace com trechos indexados lexicalmente.
def make_workspace_with_chunk(text: str = "O prazo de submissão é de 30 dias.") -> int:
    workspace = WorkspaceService().create("Workspace Chat")
    source = SourceRepository().create(
        workspace_id=workspace.id,
        source_kind=SourceKind.UPLOADED_PDF,
        title="Edital de Teste",
        status=SourceStatus.READY,
    )
    ChunkRepository().create_many(
        workspace_id=workspace.id,
        source_id=source.id,
        drafts=[
            ChunkDraft(
                chunk_index=0,
                text=text,
                char_start=0,
                char_end=len(text),
                page_number=3,
                section_title="",
                chunk_hash="hash-chat",
            )
        ],
    )
    return workspace.id


# Monta o serviço com retriever lexical e cliente falso.
def make_service(
    workspace_id: int,
    client: FakeChatClient,
    *,
    history_turns: int = 6,
) -> ChatService:
    settings = replace(get_settings(), rag_history_turns=history_turns)
    repository = ChunkRepository()
    retriever = Retriever(
        settings=settings,
        chunk_repository=repository,
        embedder=None,
    )
    return ChatService(
        settings=settings,
        chunk_repository=repository,
        retriever=retriever,
        client=client,
    )


# Responde com citação da fonte recuperada.
def test_ask_returns_answer_with_citation(isolated_database) -> None:
    init_db()
    workspace_id = make_workspace_with_chunk()
    client = FakeChatClient("O prazo é de 30 dias [F1].")

    answer = make_service(workspace_id, client).ask(workspace_id, "Qual o prazo?")

    assert answer.answer == "O prazo é de 30 dias [F1]."
    assert answer.mode == RetrievalMode.LEXICAL
    assert answer.model == get_settings().ollama_model
    assert answer.retrieved_count == 1
    assert answer.citations
    assert answer.citations[0].marker == "F1"
    assert answer.citations[0].page_number == 3
    assert client.calls == 1


# Responde com orientação geral quando não há fontes indexadas.
def test_ask_without_sources_calls_model(isolated_database) -> None:
    init_db()
    workspace = WorkspaceService().create("Workspace Vazio")
    client = FakeChatClient("Posso sugerir uma estrutura geral.")

    answer = make_service(workspace.id, client).ask(workspace.id, "Qual o prazo?")

    assert answer.answer == "Posso sugerir uma estrutura geral."
    assert answer.citations == []
    assert answer.retrieved_count == 0
    assert answer.mode is None
    assert NO_INDEXED_SOURCES_WARNING in answer.warnings
    assert client.calls == 1
    assert "Nenhum trecho de fonte indexada" in client.messages[0].content
    assert "Fontes disponíveis" not in client.messages[-1].content


# Responde mesmo quando há fontes, mas nenhum trecho relevante.
def test_ask_without_relevant_chunks_calls_model(isolated_database) -> None:
    init_db()
    workspace_id = make_workspace_with_chunk()
    client = FakeChatClient("Sugestão geral sem citar fontes.")

    answer = make_service(workspace_id, client).ask(
        workspace_id,
        "xyzabc",
    )

    assert answer.answer == "Sugestão geral sem citar fontes."
    assert answer.citations == []
    assert answer.retrieved_count == 0
    assert answer.mode == RetrievalMode.LEXICAL
    assert NO_RELEVANT_EXCERPTS_WARNING in answer.warnings
    assert client.calls == 1


# Limita o histórico enviado ao modelo.
def test_history_is_trimmed(isolated_database) -> None:
    init_db()
    workspace_id = make_workspace_with_chunk()
    client = FakeChatClient("Resposta [F1].")
    history = [
        ChatMessage(role="user", content="antiga 1"),
        ChatMessage(role="assistant", content="resposta 1"),
        ChatMessage(role="user", content="antiga 2"),
        ChatMessage(role="assistant", content="resposta 2"),
    ]

    make_service(workspace_id, client, history_turns=1).ask(
        workspace_id,
        "Qual o prazo?",
        history=history,
    )

    assert len(client.messages) == 4
    assert client.messages[0].role == "system"
    assert client.messages[1].content == "antiga 2"
    assert client.messages[2].content == "resposta 2"


# Exibe a situação do índice.
def test_status(isolated_database) -> None:
    init_db()
    workspace_id = make_workspace_with_chunk()

    status = make_service(workspace_id, FakeChatClient()).status(workspace_id)

    assert status.sources_total == 1
    assert status.sources_ready == 1
    assert status.chunks_total == 1
    assert status.chunks_embedded == 0


# Rejeita pergunta vazia.
def test_empty_question(isolated_database) -> None:
    init_db()
    workspace_id = make_workspace_with_chunk()

    with pytest.raises(ChatServiceError):
        make_service(workspace_id, FakeChatClient()).ask(workspace_id, "  ")


# Rejeita workspace inexistente.
def test_missing_workspace(isolated_database) -> None:
    init_db()

    with pytest.raises(WorkspaceNotFoundError):
        make_service(1, FakeChatClient()).ask(99, "Qual o prazo?")
