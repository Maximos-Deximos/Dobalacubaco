# Testes da divisão de conteúdo em trechos pesquisáveis.

from datetime import UTC, datetime

import pytest

from app.rag.chunker import Chunker
from app.schemas.source import ExtractedSegment, SourceSnapshot


# Monta um snapshot mínimo para os testes de chunking.
def make_snapshot(
    text: str,
    segments: list[ExtractedSegment] | None = None,
) -> SourceSnapshot:
    return SourceSnapshot(
        id=1,
        source_id=1,
        raw_path="/tmp/source.pdf",
        content_text=text,
        segments=segments or [],
        metadata={"title": "Edital"},
        fetched_at=datetime.now(UTC),
    )


# Cria trechos com sobreposição e deslocamentos corretos.
def test_chunks_long_text_with_overlap() -> None:
    text = " ".join(["requisito"] * 200)
    snapshot = make_snapshot(
        text,
        [
            ExtractedSegment(
                kind="section",
                index=1,
                title="Requisitos",
                text=text,
                start_offset=0,
                end_offset=len(text),
            )
        ],
    )

    drafts = Chunker(chunk_chars=300, overlap=50).chunk(snapshot)

    assert len(drafts) > 1
    assert all(len(draft.text) <= 300 for draft in drafts)
    assert [draft.chunk_index for draft in drafts] == list(range(len(drafts)))
    assert drafts[0].section_title == "Requisitos"
    assert drafts[0].chunk_hash
    assert drafts[1].char_start < drafts[0].char_end


# Preserva o número da página e os deslocamentos de PDFs.
def test_chunks_pdf_pages_preserve_page_numbers() -> None:
    first = "Primeira página com requisitos."
    second = "Segunda página com prazos."
    text = f"{first}\n\n{second}"
    snapshot = make_snapshot(
        text,
        [
            ExtractedSegment(
                kind="page",
                index=1,
                title="Página 1",
                text=first,
                start_offset=0,
                end_offset=len(first),
            ),
            ExtractedSegment(
                kind="page",
                index=2,
                title="Página 2",
                text=second,
                start_offset=len(first) + 2,
                end_offset=len(text),
            ),
        ],
    )

    drafts = Chunker(chunk_chars=500, overlap=50).chunk(snapshot)

    assert len(drafts) == 2
    assert drafts[0].page_number == 1
    assert drafts[1].page_number == 2
    assert drafts[1].char_start == len(first) + 2
    assert drafts[1].section_title == ""


# Usa o texto do snapshot quando não há segmentos.
def test_uses_snapshot_text_without_segments() -> None:
    snapshot = make_snapshot("Conteúdo sem segmentos.")

    drafts = Chunker(chunk_chars=500, overlap=50).chunk(snapshot)

    assert len(drafts) == 1
    assert drafts[0].text == "Conteúdo sem segmentos."
    assert drafts[0].section_title == "Edital"


# Ignora conteúdo vazio.
def test_empty_snapshot_returns_no_chunks() -> None:
    snapshot = make_snapshot("   ")

    assert Chunker().chunk(snapshot) == []


# Rejeita parâmetros inválidos.
def test_rejects_invalid_chunk_parameters() -> None:
    with pytest.raises(ValueError):
        Chunker(chunk_chars=100, overlap=100)
