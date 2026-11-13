# Cliente para a API de mensagens da Anthropic.

from __future__ import annotations

from typing import Any

import httpx

from app.ai.http_utils import extract_error_detail
from app.ai.provider import (
    AiError,
    AiModelError,
    AiResponseError,
    AiUnavailableError,
    AiUnsupportedError,
    normalize_messages,
)
from app.schemas.rag import ChatMessage

# Versão da API exigida pela Anthropic.
ANTHROPIC_VERSION = "2023-06-01"


# Cliente de chat da Anthropic; embeddings não são oferecidos pela API.
class AnthropicClient:
    name = "anthropic"

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.anthropic.com/v1",
        timeout: int = 120,
        max_tokens: int = 2048,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.transport = transport

    # Lista os modelos disponíveis para a chave informada.
    def list_models(self) -> list[str]:
        payload = self._request("GET", "/models")
        models = payload.get("data", [])
        if not isinstance(models, list):
            raise AiResponseError(
                "A Anthropic retornou uma lista de modelos inválida."
            )

        names: list[str] = []
        for item in models:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("id") or "").strip()
            if model_id:
                names.append(model_id)
        return names

    # Envia uma conversa e devolve o texto da resposta.
    def chat(
        self,
        model: str,
        messages: list[ChatMessage | dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int | None = None,
    ) -> str:
        system_parts: list[str] = []
        conversation: list[dict[str, str]] = []

        for message in normalize_messages(messages):
            role = str(message.get("role") or "user")
            content = str(message.get("content") or "")
            if role == "system":
                if content.strip():
                    system_parts.append(content.strip())
                continue
            # A Anthropic só aceita os papéis user e assistant.
            conversation.append(
                {
                    "role": "assistant" if role == "assistant" else "user",
                    "content": content,
                }
            )

        if not conversation:
            raise AiResponseError(
                "A conversa enviada à Anthropic não possui mensagens de usuário."
            )

        body: dict[str, Any] = {
            "model": model,
            "messages": conversation,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature,
        }
        if system_parts:
            body["system"] = "\n\n".join(system_parts)

        payload = self._request("POST", "/messages", body)
        content = payload.get("content")
        if not isinstance(content, list):
            raise AiResponseError("A Anthropic não retornou o conteúdo da resposta.")

        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)

        answer = "".join(parts).strip()
        if not answer:
            raise AiResponseError("A Anthropic retornou uma resposta vazia.")
        return answer

    # A Anthropic não oferece endpoint de embeddings.
    def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        raise AiUnsupportedError(
            "A Anthropic não oferece embeddings; configure um provedor de "
            "embedding local (ollama) ou outro provedor externo compatível."
        )

    # Executa uma requisição e valida o envelope JSON devolvido.
    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=headers,
                transport=self.transport,
            ) as client:
                response = client.request(method, path, json=payload)
        except httpx.RequestError as exc:
            raise AiUnavailableError(
                f"Não foi possível conectar à Anthropic em "
                f"{self.base_url}: {exc}"
            ) from exc

        if response.status_code >= 400:
            detail = extract_error_detail(response)
            if response.status_code == 404:
                raise AiModelError(
                    f"Modelo ou recurso não encontrado na Anthropic: {detail}"
                )
            if response.status_code in {401, 403, 429, 529}:
                raise AiUnavailableError(
                    f"A Anthropic recusou a requisição: {detail}"
                )
            raise AiError(
                f"A Anthropic respondeu com status "
                f"{response.status_code}: {detail}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise AiResponseError(
                "A Anthropic retornou uma resposta sem JSON."
            ) from exc
        if not isinstance(data, dict):
            raise AiResponseError("A Anthropic retornou um JSON inesperado.")
        return data
