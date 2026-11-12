# Estruturas internas do pipeline de ingestão.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.schemas.source import ExtractedSegment


# Recurso baixado da web ou lido de um arquivo local.
@dataclass(slots=True)
class FetchedResource:
    content: bytes
    content_type: str
    final_url: str
    status_code: int
    headers: dict[str, str] = field(default_factory=dict)


# Conteúdo documental extraído de HTML ou PDF.
@dataclass(slots=True)
class ExtractedDocument:
    title: str
    content_text: str
    segments: list[ExtractedSegment]
    page_count: int
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
