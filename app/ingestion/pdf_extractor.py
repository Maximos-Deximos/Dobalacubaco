# Extração de texto por página de documentos PDF.

from __future__ import annotations

from io import BytesIO
from typing import Any

from pypdf import PdfReader

from app.ingestion.models import ExtractedDocument
from app.schemas.source import ExtractedSegment


# Erro lançado quando o PDF não pode ser lido.
class PdfExtractionError(ValueError):
    pass


# Extrai texto, metadados e segmentos por página de um PDF.
class PdfExtractor:
    def extract(self, content: bytes, url: str = "") -> ExtractedDocument:
        try:
            reader = PdfReader(BytesIO(content))
        except Exception as exc:
            raise PdfExtractionError(f"PDF inválido: {exc}") from exc

        if reader.is_encrypted:
            try:
                unlocked = reader.decrypt("")
            except Exception as exc:
                raise PdfExtractionError("PDF protegido por senha.") from exc
            if not unlocked:
                raise PdfExtractionError("PDF protegido por senha.")

        metadata = self._read_metadata(reader)
        title = str(metadata.get("title") or "").strip()
        warnings: list[str] = []
        segments: list[ExtractedSegment] = []
        parts: list[str] = []
        cursor = 0

        for page_number, page in enumerate(reader.pages, start=1):
            try:
                page_text = (page.extract_text() or "").strip()
            except Exception as exc:  # noqa: BLE001
                warnings.append(
                    f"Falha ao extrair texto da página {page_number}: {exc}"
                )
                page_text = ""

            if not page_text:
                warnings.append(
                    f"A página {page_number} não possui texto extraível."
                )
                continue

            segment_text = page_text
            if parts:
                cursor += 2
            start_offset = cursor
            cursor += len(segment_text)

            segments.append(
                ExtractedSegment(
                    kind="page",
                    index=page_number,
                    title=f"Página {page_number}",
                    text=segment_text,
                    start_offset=start_offset,
                    end_offset=cursor,
                )
            )
            parts.append(segment_text)

        content_text = "\n\n".join(parts)
        if not content_text:
            warnings.append(
                "O PDF não possui texto extraível; pode ser necessário aplicar OCR."
            )

        return ExtractedDocument(
            title=title,
            content_text=content_text,
            segments=segments,
            page_count=len(reader.pages),
            metadata={**metadata, "url": url},
            warnings=warnings,
        )

    # Converte os metadados do PDF em um dicionário simples.
    def _read_metadata(self, reader: PdfReader) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        raw = reader.metadata
        if raw is None:
            return metadata

        for key, value in raw.items():
            normalized_key = str(key).lstrip("/").lower()
            metadata[normalized_key] = str(value)

        return metadata
