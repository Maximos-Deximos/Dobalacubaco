# Cliente HTTP para o serviço local do Ollama.

from __future__ import annotations

from typing import Any

import httpx

from app.ai.provider import (
    AiError,
    AiModelError,
    AiResponseError,
    AiUnavailableError,
    normalize_messages,
)
from app.schemas.rag import ChatMessage


# Erro base de comunicação com o Ollama.
class OllamaError(AiError):
    pass


# Erro de conexão, timeout ou indisponibilidade do serviço.
class OllamaUnavailableError(OllamaError, AiUnavailableError):
    pass


# Erro quando o modelo solicitado não está instalado.
class OllamaModelError(OllamaError, AiModelError):
    pass


# Erro quando a resposta do Ollama não tem o formato esperado.
class OllamaResponseError(OllamaError, AiResponseError):
    pass


# Cliente mínimo para chat e embeddings locais.
class OllamaClient:
    name = "ollama"

    def __init__(
        self,
        host: str = "http://127.0.0.1:11434",
        timeout: int = 120,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.host = host.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    # Lista os nomes dos modelos instalados.
    def list_models(self) -> list[str]:
        payload = self._request("GET", "/api/tags")
        models = payload.get("models", [])
        if not isinstance(models, list):
            raise OllamaResponseError("O Ollama retornou uma lista de modelos inválida.")

        names: list[str] = []
        for item in models:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("model") or "").strip()
            if name:
                names.append(name)
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
        options: dict[str, Any] = {"temperature": temperature}
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        payload = self._request(
            "POST",
            "/api/chat",
            {
                "model": model,
                "messages": normalize_messages(messages),
                "stream": False,
                # Evita que modelos com raciocínio gastem minutos antes da resposta.
                "think": False,
                "options": options,
            },
        )

        message = payload.get("message")
        if not isinstance(message, dict):
            raise OllamaResponseError("O Ollama não retornou uma mensagem de chat.")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise OllamaResponseError("O Ollama retornou uma resposta vazia.")
        return content.strip()

    # Gera embeddings para uma lista de textos.
    def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        payload = self._request(
            "POST",
            "/api/embed",
            {
                "model": model,
                "input": texts,
            },
        )
        embeddings = payload.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise OllamaResponseError(
                "O Ollama retornou uma quantidade inválida de embeddings."
            )

        normalized: list[list[float]] = []
        for embedding in embeddings:
            if not isinstance(embedding, list) or not embedding:
                raise OllamaResponseError("O Ollama retornou um embedding inválido.")
            try:
                normalized.append([float(value) for value in embedding])
            except (TypeError, ValueError) as exc:
                raise OllamaResponseError(
                    "O Ollama retornou valores de embedding inválidos."
                ) from exc
        return normalized

    # Executa uma requisição e valida o envelope JSON devolvido.
    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            with httpx.Client(
                base_url=self.host,
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = client.request(method, path, json=payload)
        except httpx.RequestError as exc:
            raise OllamaUnavailableError(
                f"Não foi possível conectar ao Ollama em {self.host}: {exc}"
            ) from exc

        if response.status_code >= 400:
            detail = self._error_detail(response)
            if response.status_code == 404 or "not found" in detail.lower():
                raise OllamaModelError(
                    f"Modelo ou recurso não encontrado no Ollama: {detail}"
                )
            if response.status_code in {401, 403}:
                raise OllamaUnavailableError(
                    f"O Ollama recusou a requisição: {detail}"
                )
            raise OllamaError(
                f"O Ollama respondeu com status {response.status_code}: {detail}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise OllamaResponseError("O Ollama retornou uma resposta sem JSON.") from exc
        if not isinstance(data, dict):
            raise OllamaResponseError("O Ollama retornou um JSON inesperado.")
        return data

    # Extrai uma mensagem de erro legível do corpo da resposta.
    def _error_detail(self, response: httpx.Response) -> str:
        try:
            data = response.json()
        except ValueError:
            return response.text.strip() or response.reason_phrase

        if isinstance(data, dict):
            error = data.get("error")
            if isinstance(error, str) and error.strip():
                return error.strip()
        return response.text.strip() or response.reason_phrase
