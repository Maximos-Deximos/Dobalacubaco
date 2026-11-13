# Fábrica que monta os provedores de IA a partir das configurações.

from __future__ import annotations

import httpx

from app.ai.anthropic_client import AnthropicClient
from app.ai.gemini_client import GeminiClient
from app.ai.ollama_client import OllamaClient
from app.ai.openai_client import OpenAIClient
from app.ai.provider import (
    OPENAI_COMPATIBLE_BASE_URLS,
    AiProvider,
)
from app.config import Settings

# Endereços padrão dos provedores que não usam o formato da OpenAI.
DEFAULT_BASE_URLS = {
    "anthropic": "https://api.anthropic.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
}


# Confere a chave de API antes de criar clientes externos.
def _require_api_key(api_key: str, provider: str) -> str:
    key = api_key.strip()
    if not key:
        raise ValueError(
            f"O provedor '{provider}' exige uma chave de API. "
            "Defina AI_API_KEY (ou a variável específica do provedor) no .env."
        )
    return key


# Cria o provedor usado para chat.
def build_chat_provider(
    settings: Settings,
    *,
    transport: httpx.BaseTransport | None = None,
) -> AiProvider:
    provider = settings.ai_provider

    if provider == "ollama":
        return OllamaClient(
            host=settings.ollama_host,
            timeout=settings.ai_timeout,
            transport=transport,
        )

    if provider in OPENAI_COMPATIBLE_BASE_URLS:
        return OpenAIClient(
            _require_api_key(settings.ai_api_key, provider),
            base_url=(
                settings.ai_base_url
                or OPENAI_COMPATIBLE_BASE_URLS[provider]
            ),
            timeout=settings.ai_timeout,
            transport=transport,
            name=provider,
        )

    if provider == "anthropic":
        return AnthropicClient(
            _require_api_key(settings.ai_api_key, provider),
            base_url=settings.ai_base_url or DEFAULT_BASE_URLS["anthropic"],
            timeout=settings.ai_timeout,
            max_tokens=settings.ai_max_tokens,
            transport=transport,
        )

    if provider == "gemini":
        return GeminiClient(
            _require_api_key(settings.ai_api_key, provider),
            base_url=settings.ai_base_url or DEFAULT_BASE_URLS["gemini"],
            timeout=settings.ai_timeout,
            transport=transport,
        )

    raise ValueError(f"Provedor de chat desconhecido: {provider}")


# Cria o provedor de embeddings; devolve None quando desativado.
def build_embed_provider(
    settings: Settings,
    *,
    transport: httpx.BaseTransport | None = None,
) -> AiProvider | None:
    provider = settings.ai_embed_provider

    if provider == "none":
        return None

    if provider == "ollama":
        return OllamaClient(
            host=settings.ollama_host,
            timeout=settings.ai_timeout,
            transport=transport,
        )

    if provider == "openai":
        return OpenAIClient(
            _require_api_key(settings.ai_embed_api_key, provider),
            base_url=(
                settings.ai_embed_base_url
                or OPENAI_COMPATIBLE_BASE_URLS["openai"]
            ),
            timeout=settings.ai_timeout,
            transport=transport,
            name="openai-embedding",
        )

    if provider == "gemini":
        return GeminiClient(
            _require_api_key(settings.ai_embed_api_key, provider),
            base_url=settings.ai_embed_base_url or DEFAULT_BASE_URLS["gemini"],
            timeout=settings.ai_timeout,
            transport=transport,
        )

    raise ValueError(f"Provedor de embedding desconhecido: {provider}")
