# Testes do cliente HTTP local do Ollama.

import httpx
import pytest
import respx

from app.ai.ollama_client import (
    OllamaClient,
    OllamaError,
    OllamaModelError,
    OllamaResponseError,
    OllamaUnavailableError,
)
from app.schemas.rag import ChatMessage

BASE_URL = "http://127.0.0.1:11434"


# Cria o cliente apontando para o host simulado.
def make_client() -> OllamaClient:
    return OllamaClient(host=BASE_URL, timeout=5)


# Lista modelos instalados.
@respx.mock
def test_list_models() -> None:
    respx.get(f"{BASE_URL}/api/tags").mock(
        return_value=httpx.Response(
            200,
            json={"models": [{"name": "qwen3.5:4b"}, {"name": "bge-m3"}]},
        )
    )

    assert make_client().list_models() == ["qwen3.5:4b", "bge-m3"]


# Envia chat sem streaming e devolve o conteúdo.
@respx.mock
def test_chat() -> None:
    route = respx.post(f"{BASE_URL}/api/chat").mock(
        return_value=httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": "Resposta [F1]"}},
        )
    )

    answer = make_client().chat(
        "qwen3.5:4b",
        [ChatMessage(role="user", content="Pergunta")],
        temperature=0.2,
    )

    assert answer == "Resposta [F1]"
    request = route.calls[0].request
    assert b'"stream":false' in request.content
    assert b'"think":false' in request.content
    assert b'"temperature":0.2' in request.content


# Gera embeddings em lote.
@respx.mock
def test_embed() -> None:
    respx.post(f"{BASE_URL}/api/embed").mock(
        return_value=httpx.Response(
            200,
            json={"embeddings": [[0.1, 0.2], [0.3, 0.4]]},
        )
    )

    embeddings = make_client().embed("bge-m3", ["um", "dois"])

    assert embeddings == [[0.1, 0.2], [0.3, 0.4]]


# Lista vazia não chama o Ollama.
def test_embed_empty_list() -> None:
    assert make_client().embed("bge-m3", []) == []


# Converte falha de conexão em erro de indisponibilidade.
@respx.mock
def test_connection_error() -> None:
    respx.post(f"{BASE_URL}/api/chat").mock(
        side_effect=httpx.ConnectTimeout("timeout")
    )

    with pytest.raises(OllamaUnavailableError):
        make_client().chat("qwen3.5:4b", [{"role": "user", "content": "oi"}])


# Converte 404 em erro de modelo ausente.
@respx.mock
def test_model_not_found() -> None:
    respx.post(f"{BASE_URL}/api/chat").mock(
        return_value=httpx.Response(
            404,
            json={"error": "model 'bge-m3' not found"},
        )
    )

    with pytest.raises(OllamaModelError):
        make_client().chat("bge-m3", [{"role": "user", "content": "oi"}])


# Rejeita JSON inválido.
@respx.mock
def test_invalid_json() -> None:
    respx.get(f"{BASE_URL}/api/tags").mock(
        return_value=httpx.Response(200, content=b"nao e json")
    )

    with pytest.raises(OllamaResponseError):
        make_client().list_models()


# Rejeita quantidade divergente de embeddings.
@respx.mock
def test_invalid_embedding_count() -> None:
    respx.post(f"{BASE_URL}/api/embed").mock(
        return_value=httpx.Response(200, json={"embeddings": [[0.1]]})
    )

    with pytest.raises(OllamaResponseError):
        make_client().embed("bge-m3", ["um", "dois"])


# Repassa erros HTTP genéricos.
@respx.mock
def test_generic_http_error() -> None:
    respx.get(f"{BASE_URL}/api/tags").mock(
        return_value=httpx.Response(500, text="falha interna")
    )

    with pytest.raises(OllamaError):
        make_client().list_models()
