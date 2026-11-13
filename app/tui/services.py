# Container de serviços compartilhados pelas telas da TUI.

from __future__ import annotations

from dataclasses import dataclass

from app.application.chat_service import ChatService
from app.application.diagnostics_service import DiagnosticsService
from app.application.indexing_service import IndexingService
from app.application.inspection_service import InspectionService
from app.application.proposal_service import ProposalService
from app.application.source_service import SourceIngestionService
from app.application.workspace_service import WorkspaceService
from app.config import Settings, get_settings
from app.memory.user_repository import UserRepository


@dataclass(slots=True)
class TuiServices:
    settings: Settings
    workspaces: WorkspaceService
    sources: SourceIngestionService
    indexing: IndexingService
    chat: ChatService
    proposals: ProposalService
    users: UserRepository
    diagnostics: DiagnosticsService
    inspection: InspectionService


# Monta os serviços reais a partir das configurações locais.
def build_services(settings: Settings | None = None) -> TuiServices:
    settings = settings or get_settings()
    return TuiServices(
        settings=settings,
        workspaces=WorkspaceService(),
        sources=SourceIngestionService(settings),
        indexing=IndexingService(settings),
        chat=ChatService(settings),
        proposals=ProposalService(),
        users=UserRepository(settings.database_url),
        diagnostics=DiagnosticsService(settings),
        inspection=InspectionService(settings),
    )
