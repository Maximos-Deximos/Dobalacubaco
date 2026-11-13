# Cliente para APIs compatíveis com a OpenAI (OpenAI, OpenRouter, Groq etc.).

from __future__ import annotations

from typing import Any

import httpx

from app.ai.http_utils import coerce_embeddings, extract_error_detail
from app.ai.provider import (
    AiError,
    AiModelError,
    AiResponseError,
    AiUnavailableError,
    normalize_messages,
)
from app.schemas.rag import ChatMessage


# Cliente HTTP para o formato de chat e embeddings da OpenAI.
class OpenAIClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.openai.com/v1",
        timeout: int = 120,
        transport: httpx.BaseTransport | None = None,
        name: str = "openai",
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport
        self.name = name
        self.extra_headers = extra_headers or {}

    # Lista os modelos disponíveis no provedor.
    def list_models(self) -> list[str]:
        payload = self._request("GET", "/models")
        models = payload.get("data", [])
        if not isinstance(models, list):
            raise AiResponseError(
                f"O provedor {self.name} retornou uma lista de modelos inválida."
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
        body: dict[str, Any] = {
            "model": model,
            "messages": normalize_messages(messages),
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens

        payload = self._request("POST", "/chat/completions", body)
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise AiResponseError(
                f"O provedor {self.name} não retornou uma escolha de chat."
            )

        first = choices[0]
        message = first.get("message") if isinstance(first, dict) else None
        if not isinstance(message, dict):
            raise AiResponseError(
                f"O provedor {self.name} não retornou uma mensagem de chat."
            )

        content = message.get("content")
        text = self._content_to_text(content)
        if not text:
            raise AiResponseError(
                f"O provedor {self.name} retornou uma resposta vazia."
            )
        return text

    # Gera embeddings para uma lista de textos.
    def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        payload = self._request(
            "POST",
            "/embeddings",
            {
                "model": model,
                "input": texts,
            },
        )
        data = payload.get("data")
        if not isinstance(data, list):
            raise AiResponseError(
                f"O provedor {self.name} não retornou embeddings."
            )

        # A API pode devolver os itens fora de ordem; reordena pelo índice.
        ordered: list[Any] = [None] * len(texts)
        for item in data:
            if not isinstance(item, dict):
                continue
            index = item.get("index", 0)
            if not isinstance(index, int) or not 0 <= index < len(texts):
                continue
            ordered[index] = item.get("embedding")

        return coerce_embeddings(ordered, len(texts), self.name)

    # Normaliza o conteúdo textual devolvido pela API.
    def _content_to_text(self, content: Any) -> str:
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    parts.append(part["text"])
            return "".join(parts).strip()
        return ""

    # Executa uma requisição e valida o envelope JSON devolvido.
    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **self.extra_headers,
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
                f"Não foi possível conectar ao provedor {self.name} "
                f"em {self.base_url}: {exc}"
            ) from exc

        if response.status_code >= 400:
            detail = extract_error_detail(response)
            if response.status_code == 404:
                raise AiModelError(
                    f"Modelo ou recurso não encontrado no provedor "
                    f"{self.name}: {detail}"
                )
            if response.status_code in {401, 403, 429}:
                raise AiUnavailableError(
                    f"O provedor {self.name} recusou a requisição: {detail}"
                )
            raise AiError(
                f"O provedor {self.name} respondeu com status "
                f"{response.status_code}: {detail}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise AiResponseError(
                f"O provedor {self.name} retornou uma resposta sem JSON."
            ) from exc
        if not isinstance(data, dict):
            raise AiResponseError(
                f"O provedor {self.name} retornou um JSON inesperado."
            )
        return data
