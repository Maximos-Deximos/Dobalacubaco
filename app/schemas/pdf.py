# Modelos do preenchimento assistido de formulários PDF.

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# Tipos de campo reconhecidos em um AcroForm.
class PdfFieldType(str, Enum):
    TEXT = "text"
    TEXTAREA = "textarea"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    CHOICE = "choice"
    SIGNATURE = "signature"
    UNKNOWN = "unknown"


# Ciclo de vida da sessão de preenchimento.
class PdfSessionStatus(str, Enum):
    DRAFT = "draft"
    SUGGESTED = "suggested"
    REVIEWING = "reviewing"
    READY = "ready"
    FILLED = "filled"
    FAILED = "failed"


# Estado da geração progressiva de sugestões.
class PdfGenerationStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Estado individual de cada campo revisado.
class PdfFieldStatus(str, Enum):
    PENDING = "pending"
    SUGGESTED = "suggested"
    EDITED = "edited"
    APPROVED = "approved"
    SKIPPED = "skipped"
    FILLED = "filled"
    FAILED = "failed"


# Origem de uma sugestão de preenchimento.
class PdfSuggestionSource(str, Enum):
    PROFILE = "profile"
    VECTOR = "vector"
    AI = "ai"
    MANUAL = "manual"


# Opção exibida em campos de escolha.
class PdfFieldOption(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    label: str
    value: str


# Campo lido diretamente do AcroForm.
class PdfFormField(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    field_name: str
    label: str = ""
    field_type: PdfFieldType = PdfFieldType.UNKNOWN
    required: bool = False
    readonly: bool = False
    current_value: str | None = None
    options: list[PdfFieldOption] = Field(default_factory=list)
    page_number: int | None = None
    max_length: int | None = None
    warnings: list[str] = Field(default_factory=list)


# Resultado da inspeção de um PDF.
class PdfFormInspection(BaseModel):
    source_id: int
    workspace_id: int
    source_title: str = ""
    raw_path: str
    page_count: int = 0
    fields: list[PdfFormField] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# Sessão persistida de preenchimento.
class PdfFormSession(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    source_id: int
    source_title: str = ""
    instructions: str = ""
    status: PdfSessionStatus = PdfSessionStatus.DRAFT
    generation_status: PdfGenerationStatus = PdfGenerationStatus.IDLE
    generation_progress: int = 0
    generation_total: int = 0
    output_path: str | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    last_suggested_at: datetime | None = None


# Campo persistido com sugestão e valor revisado.
class PdfFieldRecord(BaseModel):
    id: int
    session_id: int
    field_name: str
    label: str = ""
    field_type: PdfFieldType = PdfFieldType.UNKNOWN
    required: bool = False
    readonly: bool = False
    options: list[PdfFieldOption] = Field(default_factory=list)
    current_value: str | None = None
    suggested_value: str | None = None
    final_value: str | None = None
    confidence: float | None = None
    rationale: str = ""
    suggestion_source: PdfSuggestionSource | None = None
    status: PdfFieldStatus = PdfFieldStatus.PENDING
    page_number: int | None = None
    max_length: int | None = None
    warnings: list[str] = Field(default_factory=list)
    revision: int = 0
    updated_at: datetime


# Sugestão produzida pelo modelo para um campo.
class PdfFieldSuggestion(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    field_name: str
    value: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str = ""


# Sessão completa com seus campos.
class PdfFormSessionDetail(PdfFormSession):
    fields: list[PdfFieldRecord] = Field(default_factory=list)


# Lote emitido durante a geração progressiva.
class PdfSuggestionBatch(BaseModel):
    session_id: int
    fields: list[PdfFieldRecord] = Field(default_factory=list)
    completed: int = 0
    total: int = 0
    done: bool = False
    generation_status: PdfGenerationStatus = PdfGenerationStatus.RUNNING
    warnings: list[str] = Field(default_factory=list)


# Resultado da gravação do PDF preenchido.
class PdfFillResult(BaseModel):
    session_id: int
    output_path: str
    fields_filled: int = 0
    fields_skipped: int = 0
    warnings: list[str] = Field(default_factory=list)


# Exemplo revisado armazenado na memória vetorial.
class PdfFieldMemory(BaseModel):
    id: int
    workspace_id: int
    source_id: int | None = None
    label: str = ""
    field_name: str = ""
    field_type: PdfFieldType = PdfFieldType.UNKNOWN
    value: str
    embedding: list[float] | None = Field(default=None, exclude=True)
    embedding_model: str | None = None
    embedding_dim: int | None = None
    usage_count: int = 1
    approved: bool = True
    created_at: datetime
    updated_at: datetime
