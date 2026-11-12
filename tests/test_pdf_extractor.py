# Testes da extração de texto de PDFs.

from pathlib import Path

import pytest

from app.ingestion.pdf_extractor import PdfExtractionError, PdfExtractor

FIXTURES = Path(__file__).parent / "fixtures" / "ingestion"


# Extrai texto e página de um PDF com conteúdo.
def test_extracts_pdf_text() -> None:
    content = (FIXTURES / "sample_edital.pdf").read_bytes()

    document = PdfExtractor().extract(content, "https://example.com/edital.pdf")

    assert "Edital de Inovacao 2026" in document.content_text
    assert document.page_count == 1
    assert len(document.segments) == 1
    assert document.segments[0].kind == "page"
    assert document.segments[0].index == 1
    assert document.metadata["url"] == "https://example.com/edital.pdf"


# Sinaliza PDF sem texto para futura etapa de OCR.
def test_scanned_pdf_warns_about_ocr() -> None:
    content = (FIXTURES / "scanned.pdf").read_bytes()

    document = PdfExtractor().extract(content)

    assert document.content_text == ""
    assert document.page_count == 1
    assert any("OCR" in warning for warning in document.warnings)


# Rejeita conteúdo que não é PDF.
def test_invalid_pdf_raises() -> None:
    with pytest.raises(PdfExtractionError):
        PdfExtractor().extract(b"nao e um pdf")
