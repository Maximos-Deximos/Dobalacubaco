# Container de serviços compartilhados pelas telas da TUI.

from __future__ import annotations

from dataclasses import dataclass

from app.ai.factory import build_chat_provider, build_embed_provider
from app.application.chat_service import ChatService
from app.application.diagnostics_service import DiagnosticsService
from app.application.indexing_service import IndexingService
from app.application.inspection_service import InspectionService
from app.application.pdf_form_service import PdfFormService
from app.application.proposal_service import ProposalService
from app.application.source_service import SourceIngestionService
from app.application.workspace_service import WorkspaceService
from app.config import Settings, get_settings
from app.ingestion.storage import SourceStorage
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
    pdf_forms: PdfFormService


# Monta os serviços reais a partir das configurações locais.
def build_services(settings: Settings | None = None) -> TuiServices:
    settings = settings or get_settings()

    # Um único cliente de chat e um único embedder são compartilhados.
    chat_provider = build_chat_provider(settings)
    embed_provider = build_embed_provider(settings)

    return TuiServices(
        settings=settings,
        workspaces=WorkspaceService(storage=SourceStorage(settings)),
        sources=SourceIngestionService(settings),
        indexing=IndexingService(settings, embedder=embed_provider),
        chat=ChatService(
            settings,
            client=chat_provider,
            embedder=embed_provider,
        ),
        proposals=ProposalService(),
        users=UserRepository(settings.database_url),
        diagnostics=DiagnosticsService(settings),
        inspection=InspectionService(settings),
        pdf_forms=PdfFormService(
            settings,
            client=chat_provider,
            embedder=embed_provider,
        ),
    )
