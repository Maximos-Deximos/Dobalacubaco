# Modelos de campos de formulário, mapeamentos e plano de preenchimento.

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


# Tipos de campo suportados pelo detector.
class FieldType(str, Enum):
    TEXT = "text"
    EMAIL = "email"
    TEL = "tel"
    NUMBER = "number"
    DATE = "date"
    TEXTAREA = "textarea"
    SELECT = "select"
    RADIO = "radio"
    CHECKBOX = "checkbox"
    CONSENT = "consent"
    UNKNOWN = "unknown"


# Ciclo de vida de um campo durante a execução.
class FieldStatus(str, Enum):
    MAPPED = "mapped"
    UNMAPPED = "unmapped"
    SKIPPED = "skipped"
    FILLED = "filled"
    FAILED = "failed"


# Campo encontrado no DOM, sem qualquer decisão da IA.
class DetectedField(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    field_id: str
    selector: str
    label: str = ""
    field_type: FieldType = FieldType.UNKNOWN
    required: bool = False
    options: list[str] = Field(default_factory=list)
    option_values: list[str] = Field(default_factory=list)
    placeholder: str | None = None
    name: str | None = None
    input_type: str | None = None
    group_name: str | None = None
    visible: bool = True
    disabled: bool = False
    readonly: bool = False


# Metadados estruturais da página inspecionada.
class PageSnapshot(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    url: str
    title: str = ""
    form_count: int = 0
    iframe_urls: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# Resultado completo da detecção de uma página.
class DetectionResult(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    page: PageSnapshot
    fields: list[DetectedField] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    # Impede que o mesmo campo seja detectado duas vezes.
    @model_validator(mode="after")
    def validate_unique_field_ids(self) -> "DetectionResult":
        ids = [field.field_id for field in self.fields]
        if len(ids) != len(set(ids)):
            raise ValueError("A detecção contém field_id duplicado.")
        return self


# Associação semântica entre um campo detectado e o perfil.
class FieldMapping(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    field_id: str
    profile_key: str | None = None
    value: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""
    status: FieldStatus = FieldStatus.MAPPED


# Plano que o usuário revisa e aprova antes do preenchimento.
class FillPlan(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    url: str
    fields: list[FieldMapping] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    unmapped: list[str] = Field(default_factory=list)

    # Impede que o mesmo campo seja preenchido duas vezes.
    @model_validator(mode="after")
    def validate_unique_field_ids(self) -> "FillPlan":
        ids = [field.field_id for field in self.fields]
        if len(ids) != len(set(ids)):
            raise ValueError("O plano contém field_id duplicado.")
        return self
