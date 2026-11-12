# Repositório responsável pela persistência de propostas e seções.

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.memory.database import session_scope
from app.memory.models import (
    ProposalModel,
    ProposalRevisionModel,
    ProposalSectionModel,
    utcnow,
)
from app.schemas.proposal import (
    Proposal,
    ProposalCreate,
    ProposalDetail,
    ProposalRevision,
    ProposalSection,
    ProposalSectionCreate,
    ProposalSectionUpdate,
)


# Erro lançado quando a proposta não existe.
class ProposalNotFoundError(LookupError):
    pass


# Erro lançado quando a seção não existe dentro da proposta.
class ProposalSectionNotFoundError(LookupError):
    pass


# Converte o modelo ORM no contrato Pydantic da proposta.
def _to_proposal(model: ProposalModel) -> Proposal:
    return Proposal.model_validate(model)


# Converte o modelo ORM no contrato Pydantic da seção.
def _to_section(model: ProposalSectionModel) -> ProposalSection:
    return ProposalSection.model_validate(model)


# Converte o modelo ORM no contrato Pydantic da revisão.
def _to_revision(model: ProposalRevisionModel) -> ProposalRevision:
    return ProposalRevision.model_validate(model)


# Monta a proposta com as seções carregadas.
def _to_detail(model: ProposalModel) -> ProposalDetail:
    return ProposalDetail(
        **_to_proposal(model).model_dump(),
        sections=[_to_section(section) for section in model.sections],
    )


# Carrega uma proposta com as seções e revisões em uma única consulta.
def _select_detail(proposal_id: int):
    return (
        select(ProposalModel)
        .options(
            selectinload(ProposalModel.sections),
            selectinload(ProposalModel.revisions),
        )
        .where(ProposalModel.id == proposal_id)
    )


# Repositório de propostas e seções.
class ProposalRepository:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url

    # Cria uma proposta com suas seções iniciais.
    def create(
        self,
        data: ProposalCreate,
        sections: list[ProposalSectionCreate],
    ) -> ProposalDetail:
        with session_scope(self.database_url) as session:
            model = ProposalModel(
                workspace_id=data.workspace_id,
                title=data.title,
                description=data.description,
            )
            session.add(model)
            session.flush()

            for section in sections:
                session.add(
                    ProposalSectionModel(
                        proposal_id=model.id,
                        key=section.key,
                        title=section.title,
                        position=section.position,
                        content=section.content,
                        status=section.status.value,
                    )
                )

            session.flush()
            loaded = session.scalar(_select_detail(model.id))
            if loaded is None:
                raise ProposalNotFoundError(
                    f"Proposta {model.id} não encontrada após a criação."
                )
            return _to_detail(loaded)

    # Busca uma proposta com todas as seções.
    def get(self, proposal_id: int) -> ProposalDetail:
        with session_scope(self.database_url) as session:
            model = session.scalar(_select_detail(proposal_id))
            if model is None:
                raise ProposalNotFoundError(
                    f"Proposta {proposal_id} não encontrada."
                )
            return _to_detail(model)

    # Lista todas as propostas em ordem de criação.
    def list_all(self) -> list[Proposal]:
        with session_scope(self.database_url) as session:
            models = session.scalars(
                select(ProposalModel).order_by(ProposalModel.id)
            ).all()
            return [_to_proposal(model) for model in models]

    # Lista as propostas de um workspace.
    def list_by_workspace(self, workspace_id: int) -> list[Proposal]:
        with session_scope(self.database_url) as session:
            models = session.scalars(
                select(ProposalModel)
                .where(ProposalModel.workspace_id == workspace_id)
                .order_by(ProposalModel.id)
            ).all()
            return [_to_proposal(model) for model in models]

    # Busca uma seção pela chave dentro da proposta.
    def get_section_by_key(
        self,
        proposal_id: int,
        key: str,
    ) -> ProposalSection:
        with session_scope(self.database_url) as session:
            model = session.scalar(
                select(ProposalSectionModel)
                .where(ProposalSectionModel.proposal_id == proposal_id)
                .where(ProposalSectionModel.key == key)
            )
            if model is None:
                raise ProposalSectionNotFoundError(
                    f"Seção '{key}' não encontrada na proposta {proposal_id}."
                )
            return _to_section(model)

    # Atualiza uma seção e registra uma revisão.
    def update_section(
        self,
        proposal_id: int,
        section_id: int,
        data: ProposalSectionUpdate,
        *,
        action: str = "update",
        actor: str = "cli",
    ) -> ProposalDetail:
        with session_scope(self.database_url) as session:
            proposal = session.scalar(_select_detail(proposal_id))
            if proposal is None:
                raise ProposalNotFoundError(
                    f"Proposta {proposal_id} não encontrada."
                )

            section = session.get(ProposalSectionModel, section_id)
            if section is None or section.proposal_id != proposal_id:
                raise ProposalSectionNotFoundError(
                    f"Seção {section_id} não encontrada na proposta {proposal_id}."
                )

            before = section.content
            changes = data.model_dump(exclude_unset=True, exclude_none=True)
            for field, value in changes.items():
                if field == "status" and value is not None:
                    value = value.value
                setattr(section, field, value)

            section.updated_at = utcnow()
            proposal.current_revision += 1
            proposal.updated_at = utcnow()

            session.add(
                ProposalRevisionModel(
                    proposal_id=proposal_id,
                    section_id=section.id,
                    action=action,
                    content_before=before,
                    content_after=section.content,
                    actor=actor,
                )
            )
            session.flush()
            loaded = session.scalar(_select_detail(proposal_id))
            if loaded is None:
                raise ProposalNotFoundError(
                    f"Proposta {proposal_id} não encontrada após a atualização."
                )
            return _to_detail(loaded)

    # Lista o histórico de revisões de uma proposta.
    def list_revisions(self, proposal_id: int) -> list[ProposalRevision]:
        with session_scope(self.database_url) as session:
            if session.get(ProposalModel, proposal_id) is None:
                raise ProposalNotFoundError(
                    f"Proposta {proposal_id} não encontrada."
                )
            models = session.scalars(
                select(ProposalRevisionModel)
                .where(ProposalRevisionModel.proposal_id == proposal_id)
                .order_by(ProposalRevisionModel.id)
            ).all()
            return [_to_revision(model) for model in models]
