# Testes dos casos de uso de propostas.

import pytest
from sqlalchemy import func, select

from app.application.proposal_service import ProposalService
from app.application.workspace_service import WorkspaceService
from app.memory.database import init_db, session_scope
from app.memory.models import ProposalRevisionModel, ProposalSectionModel
from app.memory.proposal_repository import (
    ProposalNotFoundError,
    ProposalSectionNotFoundError,
)
from app.memory.workspace_repository import WorkspaceNotFoundError
from app.schemas.proposal import ProposalStatus, SectionStatus


# Cria uma proposta com a estrutura inicial e atualiza uma seção.
def test_proposal_service_flow(isolated_database: str) -> None:
    init_db(isolated_database)
    workspace = WorkspaceService().create("Edital de Saúde", "")
    service = ProposalService()

    proposal = service.create(
        workspace.id,
        "Proposta de inovação",
        "Descrição inicial",
    )

    assert proposal.workspace_id == workspace.id
    assert proposal.status is ProposalStatus.DRAFT
    assert len(proposal.sections) == 9
    assert [section.key for section in proposal.sections][:3] == [
        "resumo",
        "entendimento",
        "solucao",
    ]

    updated = service.update_section(
        proposal.id,
        "resumo",
        content="Resumo da solução.",
        status=SectionStatus.DRAFT,
    )

    assert updated.current_revision == proposal.current_revision + 1
    assert updated.sections[0].content == "Resumo da solução."
    assert updated.sections[0].status is SectionStatus.DRAFT

    revisions = service.revisions(proposal.id)
    assert len(revisions) == 1
    assert revisions[0].section_id == updated.sections[0].id
    assert revisions[0].content_before == ""
    assert revisions[0].content_after == "Resumo da solução."
    assert revisions[0].actor == "cli"


# Lista propostas por workspace e por todos os workspaces.
def test_proposal_service_lists(isolated_database: str) -> None:
    init_db(isolated_database)
    workspace_service = WorkspaceService()
    first = workspace_service.create("Primeiro", "")
    second = workspace_service.create("Segundo", "")
    service = ProposalService()

    first_proposal = service.create(first.id, "Proposta A")
    second_proposal = service.create(second.id, "Proposta B")

    assert [item.id for item in service.list_all()] == [
        first_proposal.id,
        second_proposal.id,
    ]
    assert [item.id for item in service.list_by_workspace(second.id)] == [
        second_proposal.id
    ]
    assert [section.key for section in service.outline(first_proposal.id)][
        -1
    ] == "anexos"


# Rejeita workspace e seção inexistentes.
def test_proposal_service_rejects_missing_records(
    isolated_database: str,
) -> None:
    init_db(isolated_database)
    workspace = WorkspaceService().create("Workspace", "")
    service = ProposalService()
    proposal = service.create(workspace.id, "Proposta")

    with pytest.raises(WorkspaceNotFoundError):
        service.create(9999, "Sem workspace")

    with pytest.raises(ProposalNotFoundError):
        service.get(9999)

    with pytest.raises(ProposalSectionNotFoundError):
        service.update_section(proposal.id, "inexistente", content="x")


# Exclui a proposta, as seções e as revisões sem afetar o workspace.
def test_proposal_service_deletes_proposal_and_children(
    isolated_database: str,
) -> None:
    init_db(isolated_database)
    workspace = WorkspaceService().create("Workspace persistente", "")
    service = ProposalService()
    proposal = service.create(workspace.id, "Proposta descartável")
    service.update_section(proposal.id, "resumo", content="Conteúdo")

    deleted = service.delete(proposal.id)

    assert deleted.id == proposal.id
    assert service.list_all() == []
    assert WorkspaceService().get(workspace.id).id == workspace.id
    with pytest.raises(ProposalNotFoundError):
        service.get(proposal.id)

    with session_scope(isolated_database) as session:
        sections = session.scalar(
            select(func.count()).select_from(ProposalSectionModel)
        )
        revisions = session.scalar(
            select(func.count()).select_from(ProposalRevisionModel)
        )
    assert sections == 0
    assert revisions == 0
