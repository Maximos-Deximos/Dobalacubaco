# Testes dos clientes e da fábrica de provedores externos de IA.

from dataclasses import replace

import httpx
import pytest
import respx

from app.ai.anthropic_client import AnthropicClient
from app.ai.factory import build_chat_provider, build_embed_provider
from app.ai.gemini_client import GeminiClient
from app.ai.ollama_client import OllamaClient
from app.ai.openai_client import OpenAIClient
from app.ai.provider import (
    AiModelError,
    AiUnavailableError,
    AiUnsupportedError,
)
from app.config import Settings
from app.schemas.rag import ChatMessage

OPENAI_BASE = "https://api.openai.com/v1"
ANTHROPIC_BASE = "https://api.anthropic.com/v1"
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"


# Monta mensagens simples para os testes.
def _messages() -> list[ChatMessage]:
    return [
        ChatMessage(role="system", content="Seja objetivo."),
        ChatMessage(role="user", content="Olá"),
    ]


# A fábrica escolhe o cliente correto para cada provedor.
def test_factory_builds_expected_providers() -> None:
    ollama = build_chat_provider(Settings.from_env(env={}))
    assert isinstance(ollama, OllamaClient)

    openai = build_chat_provider(
        Settings.from_env(env={"AI_PROVIDER": "openai", "AI_API_KEY": "sk-1"})
    )
    assert isinstance(openai, OpenAIClient)
    assert openai.base_url == OPENAI_BASE

    anthropic = build_chat_provider(
        Settings.from_env(
            env={"AI_PROVIDER": "anthropic", "AI_API_KEY": "sk-ant"}
        )
    )
    assert isinstance(anthropic, AnthropicClient)

    gemini = build_chat_provider(
        Settings.from_env(env={"AI_PROVIDER": "gemini", "AI_API_KEY": "gk"})
    )
    assert isinstance(gemini, GeminiClient)


# A fábrica monta o embedder separado e aceita a desativação.
def test_factory_builds_embedding_provider() -> None:
    settings = Settings.from_env(env={})
    assert isinstance(build_embed_provider(settings), OllamaClient)

    disabled = Settings.from_env(env={"AI_EMBED_PROVIDER": "none"})
    assert build_embed_provider(disabled) is None

    openai = Settings.from_env(
        env={"AI_EMBED_PROVIDER": "openai", "AI_EMBED_API_KEY": "sk-embed"}
    )
    assert isinstance(build_embed_provider(openai), OpenAIClient)


# A fábrica recusa provedor externo sem chave, mesmo sem validar o ambiente.
def test_factory_requires_api_key() -> None:
    settings = replace(
        Settings.from_env(env={}),
        ai_provider="openai",
        ai_api_key="",
    )

    with pytest.raises(ValueError, match="chave de API"):
        build_chat_provider(settings)


# Cliente compatível com OpenAI envia a conversa e devolve o texto.
@respx.mock
def test_openai_chat_returns_content() -> None:
    route = respx.post(f"{OPENAI_BASE}/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Resposta externa"}}]},
        )
    )
    client = OpenAIClient("sk-teste", base_url=OPENAI_BASE)

    answer = client.chat(
        "gpt-4o-mini",
        _messages(),
        temperature=0.2,
        max_tokens=100,
    )

    assert answer == "Resposta externa"
    body = route.calls[0].request.read().decode()
    assert '"model":"gpt-4o-mini"' in body
    assert '"max_tokens":100' in body
    assert '"stream":false' in body


# Embeddings da OpenAI são reordenados pelo índice informado.
@respx.mock
def test_openai_embeddings_are_reordered() -> None:
    respx.post(f"{OPENAI_BASE}/embeddings").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0]},
                    {"index": 0, "embedding": [1.0, 0.0]},
                ]
            },
        )
    )
    client = OpenAIClient("sk-teste", base_url=OPENAI_BASE)

    embeddings = client.embed("text-embedding-3-small", ["a", "b"])

    assert embeddings == [[1.0, 0.0], [0.0, 1.0]]


# Erros de autenticação viram AiUnavailableError.
@respx.mock
def test_openai_reports_auth_error() -> None:
    respx.post(f"{OPENAI_BASE}/chat/completions").mock(
        return_value=httpx.Response(
            401,
            json={"error": {"message": "chave inválida"}},
        )
    )
    client = OpenAIClient("sk-errada", base_url=OPENAI_BASE)

    with pytest.raises(AiUnavailableError, match="chave inválida"):
        client.chat("gpt-4o-mini", _messages())


# Modelo inexistente vira AiModelError.
@respx.mock
def test_openai_reports_missing_model() -> None:
    respx.post(f"{OPENAI_BASE}/chat/completions").mock(
        return_value=httpx.Response(
            404,
            json={"error": {"message": "modelo não encontrado"}},
        )
    )
    client = OpenAIClient("sk-teste", base_url=OPENAI_BASE)

    with pytest.raises(AiModelError):
        client.chat("modelo-inexistente", _messages())


# A Anthropic recebe o prompt de sistema separado das mensagens.
@respx.mock
def test_anthropic_chat_separates_system_prompt() -> None:
    route = respx.post(f"{ANTHROPIC_BASE}/messages").mock(
        return_value=httpx.Response(
            200,
            json={"content": [{"type": "text", "text": "Resposta Claude"}]},
        )
    )
    client = AnthropicClient("sk-ant", base_url=ANTHROPIC_BASE)

    answer = client.chat("claude-3-5-haiku-latest", _messages())

    assert answer == "Resposta Claude"
    request = route.calls[0].request
    assert request.headers["x-api-key"] == "sk-ant"
    assert request.headers["anthropic-version"] == "2023-06-01"
    body = request.read().decode()
    assert '"system":"Seja objetivo."' in body
    assert '"max_tokens":2048' in body
    assert '"role":"user"' in body
    assert '"role":"system"' not in body


# A Anthropic não implementa embeddings.
def test_anthropic_embeddings_are_unsupported() -> None:
    client = AnthropicClient("sk-ant", base_url=ANTHROPIC_BASE)

    with pytest.raises(AiUnsupportedError):
        client.embed("qualquer", ["texto"])


# O Gemini envia contents e devolve os textos das partes.
@respx.mock
def test_gemini_chat_returns_text_parts() -> None:
    route = respx.post(
        f"{GEMINI_BASE}/models/gemini-2.0-flash:generateContent"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": "Resposta Gemini"}]}}
                ]
            },
        )
    )
    client = GeminiClient("gk", base_url=GEMINI_BASE)

    answer = client.chat("gemini-2.0-flash", _messages(), max_tokens=50)

    assert answer == "Resposta Gemini"
    body = route.calls[0].request.read().decode()
    assert '"systemInstruction"' in body
    assert '"role":"model"' not in body
    assert '"maxOutputTokens":50' in body


# O Gemini gera embeddings em lote.
@respx.mock
def test_gemini_embeddings() -> None:
    respx.post(
        f"{GEMINI_BASE}/models/text-embedding-004:batchEmbedContents"
    ).mock(
        return_value=httpx.Response(
            200,
            json={"embeddings": [{"values": [0.1, 0.2]}, {"values": [0.3, 0.4]}]},
        )
    )
    client = GeminiClient("gk", base_url=GEMINI_BASE)

    embeddings = client.embed("text-embedding-004", ["a", "b"])

    assert embeddings == [[0.1, 0.2], [0.3, 0.4]]


# Falhas de rede são convertidas em AiUnavailableError.
@respx.mock
def test_provider_network_error() -> None:
    respx.post(f"{OPENAI_BASE}/chat/completions").mock(
        side_effect=httpx.ConnectError("sem rede")
    )
    client = OpenAIClient("sk-teste", base_url=OPENAI_BASE)

    with pytest.raises(AiUnavailableError, match="sem rede"):
        client.chat("gpt-4o-mini", _messages())
