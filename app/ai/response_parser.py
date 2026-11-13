# Validação das respostas do modelo e extração das citações.

from __future__ import annotations

import re

from app.ai.promts import INSUFFICIENT_EVIDENCE
from app.schemas.rag import ChatAnswer, Citation, RetrievalHit, RetrievalMode


# Erro lançado quando o modelo devolve uma resposta inutilizável.
class ResponseParseError(ValueError):
    pass


# Remove espaços repetidos para exibir um trecho curto da fonte.
def _snippet(text: str, limit: int = 300) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


# Converte a resposta textual do Ollama em uma resposta estruturada.
def parse_chat_answer(
    raw: str,
    hits: list[RetrievalHit],
    *,
    model: str,
    mode: RetrievalMode,
    warnings: list[str] | None = None,
) -> ChatAnswer:
    answer = raw.strip()
    if not answer:
        raise ResponseParseError("O modelo retornou uma resposta vazia.")

    result_warnings = list(warnings or [])
    markers = re.findall(r"\[F(\d+)\]", answer, flags=re.IGNORECASE)

    citations: list[Citation] = []
    seen: set[int] = set()
    for marker in markers:
        index = int(marker)
        if index in seen:
            continue
        seen.add(index)

        if index < 1 or index > len(hits):
            result_warnings.append(
                f"A resposta citou uma fonte inexistente: [F{index}]."
            )
            continue

        hit = hits[index - 1]
        citations.append(
            Citation(
                marker=f"F{index}",
                chunk_id=hit.chunk.id,
                source_id=hit.chunk.source_id,
                source_title=hit.source_title,
                source_url=hit.source_url,
                page_number=hit.chunk.page_number,
                section_title=hit.chunk.section_title,
                snippet=_snippet(hit.chunk.text),
            )
        )

    if (
        hits
        and not citations
        and not answer.startswith(INSUFFICIENT_EVIDENCE)
    ):
        result_warnings.append(
            "A resposta não incluiu citações válidas; confira as fontes recuperadas."
        )

    return ChatAnswer(
        answer=answer,
        citations=citations,
        mode=mode,
        model=model,
        retrieved_count=len(hits),
        warnings=result_warnings,
    )
