# Modelos de dados das fontes ingeridas de editais.

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# Origem e formato da fonte ingerida.
class SourceKind(str, Enum):
    WEB_PAGE = "web_page"
    WEB_PDF = "web_pdf"
    UPLOADED_HTML = "uploaded_html"
    UPLOADED_PDF = "uploaded_pdf"


# Ciclo de vida da ingestão de uma fonte.
class SourceStatus(str, Enum):
    PENDING = "pending"
    FETCHING = "fetching"
    EXTRACTING = "extracting"
    READY = "ready"
    FAILED = "failed"
    NEEDS_OCR = "needs_ocr"


# Trecho estruturado preservado para citações futuras.
class ExtractedSegment(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    kind: str = "section"
    index: int = 1
    title: str = ""
    text: str = ""
    start_offset: int = 0
    end_offset: int = 0


# Captura imutável do conteúdo de uma fonte.
class SourceSnapshot(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: int
    source_id: int
    raw_path: str
    content_text: str = ""
    segments: list[ExtractedSegment] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    page_count: int = 0
    http_status: int | None = None
    fetched_at: datetime


# Fonte registrada no workspace.
class Source(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)

    id: int
    workspace_id: int
    parent_source_id: int | None = None
    url: str | None = None
    source_kind: SourceKind
    title: str = ""
    final_url: str | None = None
    content_type: str | None = None
    sha256: str | None = None
    status: SourceStatus = SourceStatus.PENDING
    error: str | None = None
    created_at: datetime
    updated_at: datetime


# Fonte com o snapshot extraído.
class SourceDetail(Source):
    snapshot: SourceSnapshot | None = None
