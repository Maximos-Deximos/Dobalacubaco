# Casos de uso para criação e edição de propostas de solução.

from __future__ import annotations

from app.memory.proposal_repository import ProposalRepository
from app.memory.workspace_repository import WorkspaceRepository
from app.schemas.proposal import (
    DEFAULT_SECTION_BLUEPRINT,
    Proposal,
    ProposalCreate,
    ProposalDetail,
    ProposalRevision,
    ProposalSection,
    ProposalSectionCreate,
    ProposalSectionUpdate,
)


# Serviço de aplicação para propostas e seções.
class ProposalService:
    def __init__(
        self,
        repository: ProposalRepository | None = None,
        workspace_repository: WorkspaceRepository | None = None,
    ) -> None:
        self.repository = repository or ProposalRepository()
        self.workspace_repository = workspace_repository or WorkspaceRepository()

    # Cria uma proposta com a estrutura inicial de seções.
    def create(
        self,
        workspace_id: int,
        title: str,
        description: str = "",
    ) -> ProposalDetail:
        self.workspace_repository.get(workspace_id)
        data = ProposalCreate(
            workspace_id=workspace_id,
            title=title,
            description=description,
        )
        sections = [
            ProposalSectionCreate(**blueprint.model_dump())
            for blueprint in DEFAULT_SECTION_BLUEPRINT
        ]
        return self.repository.create(data, sections)

    # Busca uma proposta com suas seções.
    def get(self, proposal_id: int) -> ProposalDetail:
        return self.repository.get(proposal_id)

    # Lista todas as propostas.
    def list_all(self) -> list[Proposal]:
        return self.repository.list_all()

    # Lista as propostas de um workspace.
    def list_by_workspace(self, workspace_id: int) -> list[Proposal]:
        self.workspace_repository.get(workspace_id)
        return self.repository.list_by_workspace(workspace_id)

    # Devolve as seções ordenadas de uma proposta.
    def outline(self, proposal_id: int) -> list[ProposalSection]:
        return self.repository.get(proposal_id).sections

    # Atualiza uma seção pela sua chave estável.
    def update_section(
        self,
        proposal_id: int,
        section_key: str,
        *,
        title: str | None = None,
        content: str | None = None,
        status: str | None = None,
        position: int | None = None,
        action: str = "update",
        actor: str = "cli",
    ) -> ProposalDetail:
        section = self.repository.get_section_by_key(proposal_id, section_key)
        data = ProposalSectionUpdate(
            title=title,
            content=content,
            status=status,
            position=position,
        )
        return self.repository.update_section(
            proposal_id,
            section.id,
            data,
            action=action,
            actor=actor,
        )

    # Lista o histórico de revisões.
    def revisions(self, proposal_id: int) -> list[ProposalRevision]:
        return self.repository.list_revisions(proposal_id)
