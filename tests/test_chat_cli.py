# Testes de integração dos comandos de índice e chat.

import json
from pathlib import Path

import httpx
import respx

from app.config import get_settings
from app.main import main

FIXTURES = Path(__file__).parent / "fixtures" / "ingestion"
OLLAMA = "http://127.0.0.1:11434"


# Configura o Ollama simulado para embeddings e chat.
def mock_ollama(chat_answer: str = "O prazo é de 30 dias [F1].") -> None:
    def embed_response(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        texts = payload.get("input", [])
        return httpx.Response(
            200,
            json={"embeddings": [[1.0, 0.0] for _ in texts]},
        )

    respx.post(f"{OLLAMA}/api/embed").mock(side_effect=embed_response)
    respx.post(f"{OLLAMA}/api/chat").mock(
        return_value=httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": chat_answer,
                }
            },
        )
    )


# Prepara um workspace com o PDF de exemplo indexado.
def prepare_indexed_workspace() -> None:
    assert main(["workspace", "new", "Chat CLI"]) == 0
    assert main(
        [
            "source",
            "add-file",
            str(FIXTURES / "sample_edital.pdf"),
            "--workspace",
            "1",
        ]
    ) == 0
    assert main(["source", "index", "--workspace", "1"]) == 0


# Executa o fluxo de indexação e pergunta única em JSON.
@respx.mock
def test_chat_ask_json(isolated_database, monkeypatch, capsys) -> None:
    monkeypatch.setenv("OLLAMA_HOST", OLLAMA)
    monkeypatch.setenv("OLLAMA_EMBED_MODEL", "bge-m3")
    get_settings.cache_clear()
    mock_ollama()
    prepare_indexed_workspace()
    capsys.readouterr()

    assert main(
        [
            "chat",
            "ask",
            "Qual é o prazo?",
            "--workspace",
            "1",
            "--json",
        ]
    ) == 0

    answer = json.loads(capsys.readouterr().out)
    assert answer["answer"] == "O prazo é de 30 dias [F1]."
    assert answer["mode"] == "semantic"
    assert answer["citations"][0]["marker"] == "F1"
    assert answer["model"] == "qwen3.5:4b"


# Responde mesmo sem fontes indexadas, sem citações.
@respx.mock
def test_chat_ask_without_sources(isolated_database, monkeypatch, capsys) -> None:
    monkeypatch.setenv("OLLAMA_HOST", OLLAMA)
    get_settings.cache_clear()
    respx.post(f"{OLLAMA}/api/chat").mock(
        return_value=httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": "Posso sugerir uma estrutura geral.",
                }
            },
        )
    )

    assert main(["workspace", "new", "Chat vazio"]) == 0
    capsys.readouterr()

    assert main(
        [
            "chat",
            "ask",
            "Como estruturar a proposta?",
            "--workspace",
            "1",
            "--json",
        ]
    ) == 0

    answer = json.loads(capsys.readouterr().out)
    assert answer["answer"] == "Posso sugerir uma estrutura geral."
    assert answer["mode"] is None
    assert answer["retrieved_count"] == 0
    assert answer["citations"] == []
    assert any("Nenhuma fonte indexada" in item for item in answer["warnings"])


# Exibe a situação do índice em JSON.
@respx.mock
def test_chat_status_json(isolated_database, monkeypatch, capsys) -> None:
    monkeypatch.setenv("OLLAMA_HOST", OLLAMA)
    monkeypatch.setenv("OLLAMA_EMBED_MODEL", "bge-m3")
    get_settings.cache_clear()
    mock_ollama()
    prepare_indexed_workspace()
    capsys.readouterr()

    assert main(["chat", "status", "--workspace", "1", "--json"]) == 0

    status = json.loads(capsys.readouterr().out)
    assert status["sources_total"] == 1
    assert status["sources_ready"] == 1
    assert status["chunks_total"] > 0
    assert status["chunks_embedded"] == status["chunks_total"]


# O REPL responde e encerra com /exit.
@respx.mock
def test_chat_repl(isolated_database, monkeypatch, capsys) -> None:
    monkeypatch.setenv("OLLAMA_HOST", OLLAMA)
    monkeypatch.setenv("OLLAMA_EMBED_MODEL", "bge-m3")
    get_settings.cache_clear()
    mock_ollama()
    prepare_indexed_workspace()
    capsys.readouterr()

    prompts = iter(["Qual é o prazo?", "/sources", "/clear", "/help", "/exit"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(prompts))

    assert main(["chat", "repl", "--workspace", "1"]) == 0

    output = capsys.readouterr().out
    assert "Chat local iniciado" in output
    assert "O prazo é de 30 dias [F1]." in output
    assert "sample_edital" in output


# Informa workspace inexistente.
def test_chat_missing_workspace(isolated_database, capsys) -> None:
    assert main(["chat", "ask", "Pergunta", "--workspace", "99"]) == 1
    assert "Área de trabalho 99 não encontrada" in capsys.readouterr().err


# Informa falha de indexação em workspace inexistente.
def test_source_index_missing_workspace(isolated_database, capsys) -> None:
    assert main(["source", "index", "--workspace", "99"]) == 1
    assert "Área de trabalho 99 não encontrada" in capsys.readouterr().err
