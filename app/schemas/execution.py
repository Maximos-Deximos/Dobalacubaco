# Modelos de estado e histórico de execuções.

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# Estados possíveis de uma execução do agente.
class ExecutionStatus(str, Enum):
    IDLE = "idle"
    VALIDATING_URL = "validating_url"
    INSPECTING = "inspecting"
    DETECTING_FIELDS = "detecting_fields"
    MAPPING = "mapping"
    AWAITING_APPROVAL = "awaiting_approval"
    FILLING = "filling"
    VERIFYING = "verifying"
    AWAITING_SUBMIT = "awaiting_submit"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Registro persistido de uma execução.
class ExecutionRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    domain: str
    instructions: str
    status: ExecutionStatus
    profile_snapshot: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    created_at: datetime
    updated_at: datetime


# Registro persistido do resultado de um campo em uma execução.
class ExecutionFieldRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    execution_id: int
    field_id: str
    label: str
    field_type: str
    required: bool
    options: list[str] = Field(default_factory=list)
    selector: str
    mapped_key: str | None = None
    suggested_value: str | None = None
    confidence: float | None = None
    status: str
    verified: bool = False
    error: str | None = None
