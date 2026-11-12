# Testes da extração e validação de citações.

from datetime import UTC, datetime

import pytest

from app.ai.response_parser import ResponseParseError, parse_chat_answer
from app.schemas.rag import RetrievalHit, RetrievalMode, SourceChunk


# Cria um trecho recuperado para os testes de citação.
def make_hit(chunk_id: int, text: str) -> RetrievalHit:
    return RetrievalHit(
        chunk=SourceChunk(
            id=chunk_id,
            workspace_id=1,
            source_id=1,
            chunk_index=chunk_id - 1,
            text=text,
            char_start=0,
            char_end=len(text),
            page_number=chunk_id,
            section_title="",
            chunk_hash=f"hash-{chunk_id}",
            indexed_at=datetime.now(UTC),
        ),
        source_title="Edital",
        source_url="https://example.com/edital",
        score=1.0,
        mode=RetrievalMode.SEMANTIC,
    )


# Mapeia marcadores válidos e remove citações repetidas.
def test_parses_valid_citations() -> None:
    hits = [make_hit(1, "Prazo de 30 dias."), make_hit(2, "Orçamento previsto.")]

    answer = parse_chat_answer(
        "O prazo é de 30 dias [F1]. O orçamento existe [F2] e [F1].",
        hits,
        model="qwen3.5:4b",
        mode=RetrievalMode.SEMANTIC,
    )

    assert [citation.marker for citation in answer.citations] == ["F1", "F2"]
    assert answer.citations[0].page_number == 1
    assert answer.retrieved_count == 2


# Sinaliza citação inexistente sem quebrar a resposta.
def test_invalid_citation_warns() -> None:
    answer = parse_chat_answer(
        "Resposta [F9].",
        [make_hit(1, "Trecho")],
        model="qwen3.5:4b",
        mode=RetrievalMode.LEXICAL,
    )

    assert answer.citations == []
    assert any("inexistente" in warning for warning in answer.warnings)


# Sinaliza resposta sem citações.
def test_missing_citation_warns() -> None:
    answer = parse_chat_answer(
        "Resposta sem marcador.",
        [make_hit(1, "Trecho")],
        model="qwen3.5:4b",
        mode=RetrievalMode.LEXICAL,
    )

    assert answer.citations == []
    assert any("não incluiu citações" in warning for warning in answer.warnings)


# Rejeita resposta vazia.
def test_empty_answer_raises() -> None:
    with pytest.raises(ResponseParseError):
        parse_chat_answer(
            "  ",
            [],
            model="qwen3.5:4b",
            mode=RetrievalMode.LEXICAL,
        )
