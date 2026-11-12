# Testes da extração de conteúdo HTML.

from pathlib import Path

from app.ingestion.html_extractor import HtmlExtractor

FIXTURES = Path(__file__).parent / "fixtures" / "ingestion"


# Extrai título, texto e segmento de um edital HTML.
def test_extracts_edital_content() -> None:
    content = (FIXTURES / "sample_edital.html").read_bytes()

    document = HtmlExtractor().extract(content, "https://example.com/edital")

    assert document.title == "Edital de Inovação 2026"
    assert "Apoiar soluções digitais" in document.content_text
    assert "Orçamento detalhado" in document.content_text
    assert document.page_count == 1
    assert len(document.segments) == 1
    assert document.segments[0].text == document.content_text
    assert document.metadata["url"] == "https://example.com/edital"


# Usa o texto bruto quando o extrator principal não encontra conteúdo.
def test_falls_back_to_visible_text() -> None:
    content = b"<html><body><div>Texto simples</div></body></html>"

    document = HtmlExtractor().extract(content)

    assert "Texto simples" in document.content_text


# Retorna aviso para página sem texto.
def test_empty_html_warns() -> None:
    document = HtmlExtractor().extract(b"<html><body></body></html>")

    assert document.content_text == ""
    assert document.segments == []
    assert any("não possui texto" in warning for warning in document.warnings)
