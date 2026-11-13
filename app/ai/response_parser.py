# Validação das respostas do modelo e extração das citações.

from __future__ import annotations

import json
import re

from app.ai.promts import INSUFFICIENT_EVIDENCE
from app.schemas.pdf import PdfFieldSuggestion
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
    mode: RetrievalMode | None,
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


# Erro lançado quando a resposta de sugestões de PDF é inutilizável.
class PdfSuggestionParseError(ValueError):
    pass


# Extrai o primeiro bloco JSON útil de uma resposta do modelo.
def _extract_json(raw: str) -> object:
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()

    for opening, closing in (("{", "}"), ("[", "]")):
        start = text.find(opening)
        end = text.rfind(closing)
        if start >= 0 and end > start:
            candidate = text[start : end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

    raise PdfSuggestionParseError("O modelo não retornou um JSON válido.")


# Valida e normaliza sugestões de campos de PDF.
def parse_pdf_suggestions(
    raw: str,
    fields: list,
) -> tuple[list[PdfFieldSuggestion], list[str]]:
    data = _extract_json(raw)
    if isinstance(data, dict):
        items = data.get("suggestions")
    else:
        items = data
    if not isinstance(items, list):
        raise PdfSuggestionParseError(
            "O JSON de sugestões deve conter uma lista 'suggestions'."
        )

    fields_by_name = {field.field_name: field for field in fields}
    suggestions: list[PdfFieldSuggestion] = []
    warnings: list[str] = []
    seen: set[str] = set()

    for item in items:
        if not isinstance(item, dict):
            warnings.append("Uma sugestão foi ignorada por não ser um objeto JSON.")
            continue

        field_name = str(item.get("field_name") or "").strip()
        field = fields_by_name.get(field_name)
        if field is None:
            warnings.append(f"Sugestão para campo desconhecido ignorada: {field_name}.")
            continue
        if field_name in seen:
            warnings.append(f"Sugestão duplicada ignorada para '{field_name}'.")
            continue
        seen.add(field_name)

        if field.readonly or str(getattr(field.field_type, "value", field.field_type)) == "signature":
            warnings.append(f"Campo '{field_name}' não pode ser preenchido por IA.")
            continue

        raw_value = item.get("value")
        if raw_value is None:
            value = None
        elif isinstance(raw_value, bool):
            value = "Yes" if raw_value else "Off"
        elif isinstance(raw_value, (str, int, float)):
            value = str(raw_value).strip()
        elif isinstance(raw_value, list):
            value = ", ".join(str(part).strip() for part in raw_value if str(part).strip())
        else:
            warnings.append(f"Valor inválido ignorado para '{field_name}'.")
            continue

        if value is not None:
            allowed = {option.value for option in field.options}
            if allowed and value not in allowed:
                warnings.append(
                    f"Valor '{value}' inválido para '{field_name}'; sugestão ignorada."
                )
                continue
            if field.max_length is not None and len(value) > field.max_length:
                value = value[: field.max_length]
                warnings.append(
                    f"Valor de '{field_name}' truncado para {field.max_length} caracteres."
                )

        try:
            confidence = float(item.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))
        rationale = str(item.get("rationale") or "").strip()
        suggestions.append(
            PdfFieldSuggestion(
                field_name=field_name,
                value=value,
                confidence=confidence,
                rationale=rationale,
            )
        )

    if not suggestions:
        warnings.append("O modelo não retornou sugestões utilizáveis.")
    return suggestions, warnings
