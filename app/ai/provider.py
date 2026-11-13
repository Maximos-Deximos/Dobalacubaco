# Contratos e erros comuns de todos os provedores de IA.
#
# Os serviços da aplicação dependem apenas deste protocolo, permitindo
# alternar entre o Ollama local e provedores externos por chave de API.

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.schemas.rag import ChatMessage

# Provedores de chat reconhecidos pela aplicação.
SUPPORTED_CHAT_PROVIDERS = frozenset(
    {"ollama", "openai", "openrouter", "groq", "deepseek", "anthropic", "gemini"}
)

# Provedores de embedding reconhecidos; "none" desliga a busca semântica.
SUPPORTED_EMBED_PROVIDERS = frozenset({"ollama", "openai", "gemini", "none"})

# Modelos padrão usados quando AI_MODEL ou AI_EMBED_MODEL não são informados.
DEFAULT_CHAT_MODELS = {
    "ollama": "qwen3.5:4b",
    "openai": "gpt-4o-mini",
    "openrouter": "openai/gpt-4o-mini",
    "groq": "llama-3.3-70b-versatile",
    "deepseek": "deepseek-chat",
    "anthropic": "claude-3-5-haiku-latest",
    "gemini": "gemini-2.0-flash",
}

DEFAULT_EMBED_MODELS = {
    "ollama": "bge-m3",
    "openai": "text-embedding-3-small",
    "gemini": "text-embedding-004",
}

# Endereços padrão das APIs compatíveis com a OpenAI.
OPENAI_COMPATIBLE_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "groq": "https://api.groq.com/openai/v1",
    "deepseek": "https://api.deepseek.com/v1",
}


# Erro base de comunicação com qualquer provedor de IA.
class AiError(RuntimeError):
    pass


# Erro de conexão, timeout, autenticação ou indisponibilidade do serviço.
class AiUnavailableError(AiError):
    pass


# Erro quando o modelo solicitado não existe ou não está disponível.
class AiModelError(AiError):
    pass


# Erro quando a resposta do provedor não tem o formato esperado.
class AiResponseError(AiError):
    pass


# Erro quando o provedor não oferece a operação solicitada.
class AiUnsupportedError(AiError):
    pass


# Contrato mínimo consumido pelos serviços de aplicação.
@runtime_checkable
class AiProvider(Protocol):
    name: str

    # Lista os nomes dos modelos disponíveis no provedor.
    def list_models(self) -> list[str]: ...

    # Envia uma conversa e devolve o texto da resposta.
    def chat(
        self,
        model: str,
        messages: list[ChatMessage | dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int | None = None,
    ) -> str: ...

    # Gera embeddings para uma lista de textos.
    def embed(self, model: str, texts: list[str]) -> list[list[float]]: ...


# Converte mensagens Pydantic ou dicionários em dicionários simples.
def normalize_messages(
    messages: list[ChatMessage | dict[str, str]],
) -> list[dict[str, str]]:
    return [
        message.model_dump() if isinstance(message, ChatMessage) else dict(message)
        for message in messages
    ]
