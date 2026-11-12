# Modelos de dados dos workspaces de editais.

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# Estados possíveis de um workspace.
class WorkspaceStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


# Dados necessários para criar um workspace.
class WorkspaceCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    status: WorkspaceStatus = WorkspaceStatus.ACTIVE


# Workspace devolvido pela camada de persistência.
class Workspace(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)

    id: int
    name: str
    description: str = ""
    status: WorkspaceStatus = WorkspaceStatus.ACTIVE
    created_at: datetime
    updated_at: datetime
