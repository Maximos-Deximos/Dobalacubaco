# Cliente para a API Gemini, do Google.

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


# Cliente de chat e embeddings do Google Gemini.
class GeminiClient:
    name = "gemini"

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout: int = 120,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    # Lista os modelos disponíveis para a chave informada.
    def list_models(self) -> list[str]:
        payload = self._request("GET", "/models")
        models = payload.get("models", [])
        if not isinstance(models, list):
            raise AiResponseError("O Gemini retornou uma lista de modelos inválida.")

        names: list[str] = []
        for item in models:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            # A API devolve o nome como "models/<id>".
            names.append(name.removeprefix("models/"))
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
        contents: list[dict[str, Any]] = []

        for message in normalize_messages(messages):
            role = str(message.get("role") or "user")
            content = str(message.get("content") or "")
            if role == "system":
                if content.strip():
                    system_parts.append(content.strip())
                continue
            contents.append(
                {
                    "role": "model" if role == "assistant" else "user",
                    "parts": [{"text": content}],
                }
            )

        if not contents:
            raise AiResponseError(
                "A conversa enviada ao Gemini não possui mensagens de usuário."
            )

        body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"temperature": temperature},
        }
        if system_parts:
            body["systemInstruction"] = {
                "parts": [{"text": "\n\n".join(system_parts)}]
            }
        if max_tokens is not None:
            body["generationConfig"]["maxOutputTokens"] = max_tokens

        payload = self._request(
            "POST",
            f"/models/{self._model_name(model)}:generateContent",
            body,
        )
        candidates = payload.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            feedback = payload.get("promptFeedback")
            reason = ""
            if isinstance(feedback, dict):
                reason = str(feedback.get("blockReason") or "").strip()
            detail = f" (bloqueado: {reason})" if reason else ""
            raise AiResponseError(
                f"O Gemini não retornou uma resposta{detail}."
            )

        first = candidates[0]
        content = first.get("content") if isinstance(first, dict) else None
        parts = content.get("parts") if isinstance(content, dict) else None
        if not isinstance(parts, list):
            raise AiResponseError("O Gemini não retornou o conteúdo da resposta.")

        texts: list[str] = []
        for part in parts:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                texts.append(part["text"])

        answer = "".join(texts).strip()
        if not answer:
            raise AiResponseError("O Gemini retornou uma resposta vazia.")
        return answer

    # Gera embeddings para uma lista de textos.
    def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        model_path = self._model_name(model)
        payload = self._request(
            "POST",
            f"/models/{model_path}:batchEmbedContents",
            {
                "requests": [
                    {
                        "model": f"models/{model_path}",
                        "content": {"parts": [{"text": text}]},
                    }
                    for text in texts
                ]
            },
        )
        embeddings = payload.get("embeddings")
        if not isinstance(embeddings, list):
            raise AiResponseError("O Gemini não retornou embeddings.")

        values = [
            item.get("values") if isinstance(item, dict) else None
            for item in embeddings
        ]
        return coerce_embeddings(values, len(texts), self.name)

    # Remove o prefixo "models/" quando o usuário informar o nome completo.
    def _model_name(self, model: str) -> str:
        return model.strip().removeprefix("models/")

    # Executa uma requisição e valida o envelope JSON devolvido.
    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {
            "x-goog-api-key": self.api_key,
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
                f"Não foi possível conectar ao Gemini em "
                f"{self.base_url}: {exc}"
            ) from exc

        if response.status_code >= 400:
            detail = extract_error_detail(response)
            if response.status_code == 404:
                raise AiModelError(
                    f"Modelo ou recurso não encontrado no Gemini: {detail}"
                )
            if response.status_code in {401, 403, 429}:
                raise AiUnavailableError(
                    f"O Gemini recusou a requisição: {detail}"
                )
            raise AiError(
                f"O Gemini respondeu com status "
                f"{response.status_code}: {detail}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise AiResponseError("O Gemini retornou uma resposta sem JSON.") from exc
        if not isinstance(data, dict):
            raise AiResponseError("O Gemini retornou um JSON inesperado.")
        return data
