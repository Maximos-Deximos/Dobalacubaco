# Extração de conteúdo principal de páginas HTML.

from __future__ import annotations

import re

import trafilatura
from bs4 import BeautifulSoup

from app.ingestion.models import ExtractedDocument
from app.schemas.source import ExtractedSegment


# Erro lançado quando o HTML não pode ser processado.
class HtmlExtractionError(ValueError):
    pass


# Remove espaços repetidos e linhas vazias excessivas.
def _normalize_text(value: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line).strip()


# Extrai título e conteúdo principal de um documento HTML.
class HtmlExtractor:
    def extract(self, content: bytes, url: str = "") -> ExtractedDocument:
        try:
            soup = BeautifulSoup(content, "lxml")
        except Exception as exc:
            raise HtmlExtractionError(f"HTML inválido: {exc}") from exc

        title = _normalize_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
        description = ""
        description_tag = soup.find("meta", attrs={"name": "description"})
        if description_tag is not None:
            description = str(description_tag.get("content") or "").strip()

        text = self._extract_main_text(str(soup))
        warnings: list[str] = []

        if not text:
            text = _normalize_text(soup.get_text("\n", strip=True))
            warnings.append(
                "O extrator principal não encontrou conteúdo; foi usado o texto bruto da página."
            )

        if not text:
            warnings.append("A página não possui texto extraível.")

        segments: list[ExtractedSegment] = []
        if text:
            segments.append(
                ExtractedSegment(
                    kind="section",
                    index=1,
                    title=title or "Conteúdo principal",
                    text=text,
                    start_offset=0,
                    end_offset=len(text),
                )
            )

        return ExtractedDocument(
            title=title,
            content_text=text,
            segments=segments,
            page_count=1,
            metadata={
                "url": url,
                "description": description,
            },
            warnings=warnings,
        )

    # Usa trafilatura com fallback para o texto visível do documento.
    def _extract_main_text(self, html: str) -> str:
        extracted = trafilatura.extract(
            html,
            output_format="txt",
            include_comments=False,
            include_tables=True,
            favor_recall=True,
        )
        return _normalize_text(extracted or "")
