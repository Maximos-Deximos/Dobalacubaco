# Modelos de dados da proposta de solução e suas seções.

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# Ciclo de vida de uma proposta.
class ProposalStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    COMPLETED = "completed"
    ARCHIVED = "archived"


# Ciclo de vida de uma seção da proposta.
class SectionStatus(str, Enum):
    EMPTY = "empty"
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"


# Seção inicial criada junto com uma nova proposta.
class SectionBlueprint(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    key: str
    title: str
    position: int
    content: str = ""
    status: SectionStatus = SectionStatus.EMPTY


# Estrutura inicial sugerida para uma proposta.
DEFAULT_SECTION_BLUEPRINT: tuple[SectionBlueprint, ...] = (
    SectionBlueprint(key="resumo", title="Resumo", position=1),
    SectionBlueprint(key="entendimento", title="Entendimento do edital", position=2),
    SectionBlueprint(key="solucao", title="Solução proposta", position=3),
    SectionBlueprint(key="metodologia", title="Metodologia", position=4),
    SectionBlueprint(key="cronograma", title="Cronograma", position=5),
    SectionBlueprint(key="equipe", title="Equipe", position=6),
    SectionBlueprint(key="orcamento", title="Orçamento", position=7),
    SectionBlueprint(key="sustentabilidade", title="Sustentabilidade", position=8),
    SectionBlueprint(key="anexos", title="Anexos", position=9),
)


# Dados para criar uma proposta.
class ProposalCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    workspace_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    description: str = ""


# Dados para criar uma seção.
class ProposalSectionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    key: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    position: int = Field(ge=1)
    content: str = ""
    status: SectionStatus = SectionStatus.EMPTY


# Dados para atualizar uma seção existente.
class ProposalSectionUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = None
    status: SectionStatus | None = None
    position: int | None = Field(default=None, ge=1)


# Seção persistida de uma proposta.
class ProposalSection(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)

    id: int
    proposal_id: int
    key: str
    title: str
    position: int
    content: str = ""
    status: SectionStatus = SectionStatus.EMPTY
    created_at: datetime
    updated_at: datetime


# Proposta sem o conteúdo completo das seções.
class Proposal(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)

    id: int
    workspace_id: int
    title: str
    description: str = ""
    status: ProposalStatus = ProposalStatus.DRAFT
    current_revision: int = 1
    created_at: datetime
    updated_at: datetime


# Proposta com as seções ordenadas.
class ProposalDetail(Proposal):
    sections: list[ProposalSection] = Field(default_factory=list)


# Registro imutável de uma alteração de seção.
class ProposalRevision(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    proposal_id: int
    section_id: int | None = None
    action: str
    content_before: str = ""
    content_after: str = ""
    actor: str = "cli"
    created_at: datetime
