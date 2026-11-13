# Utilidades HTTP compartilhadas pelos provedores externos de IA.

from __future__ import annotations

from typing import Any

import httpx

from app.ai.provider import AiResponseError


# Extrai uma mensagem de erro legível do corpo da resposta.
def extract_error_detail(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text.strip() or response.reason_phrase

    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, str) and error.strip():
            return error.strip()
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
        message = data.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    return response.text.strip() or response.reason_phrase


# Valida e converte uma lista de embeddings devolvida pelo provedor.
def coerce_embeddings(
    raw: Any,
    expected: int,
    provider: str,
) -> list[list[float]]:
    if not isinstance(raw, list) or len(raw) != expected:
        raise AiResponseError(
            f"O provedor {provider} retornou uma quantidade inválida de embeddings."
        )

    normalized: list[list[float]] = []
    for embedding in raw:
        if not isinstance(embedding, list) or not embedding:
            raise AiResponseError(
                f"O provedor {provider} retornou um embedding inválido."
            )
        try:
            normalized.append([float(value) for value in embedding])
        except (TypeError, ValueError) as exc:
            raise AiResponseError(
                f"O provedor {provider} retornou valores de embedding inválidos."
            ) from exc
    return normalized
