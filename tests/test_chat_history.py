# Testes da conversa persistida entre execuções do agente.

from dataclasses import replace

import pytest

from app.application.chat_service import ChatService
from app.application.workspace_service import WorkspaceService
from app.config import get_settings
from app.memory.chat_repository import ChatRepository
from app.memory.chunk_repository import ChunkRepository
from app.memory.database import init_db
from app.rag.retriever import Retriever
from app.schemas.rag import answer_from_record


# Cliente falso que registra as mensagens enviadas ao modelo.
class FakeChatClient:
    def __init__(self, answer: str = "Resposta salva.") -> None:
        self.answer = answer
        self.messages = []
        self.calls = 0

    def chat(
        self,
        model: str,
        messages,
        *,
        temperature: float = 0.1,
        max_tokens: int | None = None,
    ) -> str:
        self.calls += 1
        self.messages = messages
        return self.answer


# Monta o serviço com retriever lexical e cliente falso.
def make_service(client: FakeChatClient, *, history_turns: int = 6) -> ChatService:
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


# Grava a troca e a recupera em uma nova instância do serviço.
def test_persists_and_restores_conversation(isolated_database) -> None:
    init_db()
    workspace = WorkspaceService().create("Workspace Persistente")
    service = make_service(FakeChatClient("O prazo é de 30 dias."))

    service.ask(workspace.id, "Qual é o prazo?")

    records = make_service(FakeChatClient()).conversation(workspace.id)
    assert [record.role for record in records] == ["user", "assistant"]
    assert records[0].content == "Qual é o prazo?"
    assert records[1].content == "O prazo é de 30 dias."
    assert records[1].extra_metadata["answer"]["answer"] == "O prazo é de 30 dias."
    restored = answer_from_record(records[1])
    assert restored is not None
    assert restored.answer == "O prazo é de 30 dias."

    limited = make_service(FakeChatClient()).conversation(workspace.id, limit=1)
    assert [record.role for record in limited] == ["assistant"]


# A pergunta seguinte recebe a conversa salva como contexto.
def test_next_question_reuses_saved_history(isolated_database) -> None:
    init_db()
    workspace = WorkspaceService().create("Workspace Contexto")
    make_service(FakeChatClient("Primeira resposta.")).ask(
        workspace.id,
        "Primeira pergunta?",
    )

    client = FakeChatClient("Segunda resposta.")
    make_service(client).ask(workspace.id, "Segunda pergunta?")

    contents = [message.content for message in client.messages]
    assert any("Primeira pergunta?" in content for content in contents)
    assert any("Primeira resposta." in content for content in contents)
    assert len(make_service(FakeChatClient()).conversation(workspace.id)) == 4


# Falhas do modelo não gravam uma troca incompleta.
def test_failed_request_does_not_persist(isolated_database) -> None:
    init_db()
    workspace = WorkspaceService().create("Workspace Falha")

    class FailingClient(FakeChatClient):
        def chat(self, *args, **kwargs) -> str:
            raise RuntimeError("modelo indisponível")

    with pytest.raises(RuntimeError):
        make_service(FailingClient()).ask(workspace.id, "Pergunta sem resposta?")

    assert make_service(FakeChatClient()).conversation(workspace.id) == []


# A limpeza remove apenas a conversa do workspace selecionado.
def test_clear_only_affects_selected_workspace(isolated_database) -> None:
    init_db()
    first = WorkspaceService().create("Workspace Um")
    second = WorkspaceService().create("Workspace Dois")
    service = make_service(FakeChatClient())

    service.ask(first.id, "Pergunta um?")
    service.ask(second.id, "Pergunta dois?")

    removed = service.clear_conversation(first.id)

    assert removed == 2
    assert service.conversation(first.id) == []
    assert len(service.conversation(second.id)) == 2


# Excluir a área de trabalho remove a conversa em cascata.
def test_workspace_delete_cascades_conversation(isolated_database) -> None:
    init_db()
    workspace = WorkspaceService().create("Workspace Excluído")
    make_service(FakeChatClient()).ask(workspace.id, "Pergunta?")

    WorkspaceService().delete(workspace.id)

    assert ChatRepository().count_by_workspace(workspace.id) == 0
