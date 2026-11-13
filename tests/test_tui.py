# Testes da interface de terminal baseada em Textual.

from pathlib import Path

import pytest
from textual.widgets import DataTable, Input, TabbedContent

from app.application.diagnostics_service import DiagnosticCheck
from app.application.proposal_service import ProposalService
from app.application.workspace_service import WorkspaceService
from app.memory.database import init_db
from app.schemas.form import DetectionResult, PageSnapshot
from app.schemas.rag import ChatAnswer
from app.tui.app import ProposalTuiApp
from app.tui.screens.chat import ChatPane
from app.tui.screens.help import HelpScreen
from app.tui.screens.home import HomeScreen
from app.tui.screens.profile import ProfileEditScreen, ProfileScreen
from app.tui.screens.proposals import ProposalScreen, ProposalsScreen
from app.tui.screens.sources import SourcesPane
from app.tui.screens.tools import ToolsScreen
from app.tui.screens.workspaces import WorkspaceScreen
from app.tui.services import build_services

FIXTURES = Path(__file__).parent / "fixtures" / "ingestion"


# Prepara um workspace com uma proposta para os testes da TUI.
def _prepare_data(isolated_database: str) -> tuple[int, int]:
    init_db(isolated_database)
    workspace = WorkspaceService().create("Workspace TUI", "Descrição TUI")
    proposal = ProposalService().create(workspace.id, "Proposta TUI")
    return workspace.id, proposal.id


# Monta a aplicação com serviços reais ligados ao banco isolado.
def _build_app() -> ProposalTuiApp:
    return ProposalTuiApp(build_services())


# Exibe as áreas de trabalho cadastradas na tela inicial.
@pytest.mark.asyncio
async def test_tui_home_lists_workspaces(isolated_database: str) -> None:
    _prepare_data(isolated_database)
    app = _build_app()

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, HomeScreen)
        table = app.screen.query_one("#home-workspaces-table", DataTable)
        assert table.row_count == 1
        assert str(table.ordered_columns[1].label) == "Nome"
        row = table.get_row_at(0)
        assert row[1] == "Workspace TUI"
        assert row[2] == "Ativa"
        stats = app.screen.query_one("#home-stats")
        assert "Áreas de trabalho: 1" in str(stats.content)
        assert "Propostas: 1" in str(stats.content)


# Abre e fecha a tela de ajuda pelo atalho.
@pytest.mark.asyncio
async def test_tui_help_shortcut(isolated_database: str) -> None:
    _prepare_data(isolated_database)
    app = _build_app()

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("?")
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, HomeScreen)


# Abre uma área de trabalho e navega pelas abas.
@pytest.mark.asyncio
async def test_tui_opens_workspace_tabs(isolated_database: str) -> None:
    _prepare_data(isolated_database)
    app = _build_app()

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, WorkspaceScreen)
        assert "Workspace TUI" in str(
            app.screen.query_one("#workspace-title").content
        )

        tabs = app.screen.query_one("#workspace-tabs", TabbedContent)
        tabs.active = "tab-sources"
        await pilot.pause()
        sources = app.screen.query_one(SourcesPane)
        assert sources.query_one("#sources-table", DataTable).row_count == 0

        tabs.active = "tab-proposals"
        await pilot.pause()
        proposals_table = app.screen.query_one(
            "#workspace-proposals-table",
            DataTable,
        )
        assert proposals_table.row_count == 1
        assert proposals_table.get_row_at(0)[2] == "Rascunho"

        tabs.active = "tab-chat"
        await pilot.pause()
        assert isinstance(app.screen.query_one(ChatPane), ChatPane)

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, HomeScreen)


# Abre a tela global de propostas e lê as seções.
@pytest.mark.asyncio
async def test_tui_opens_proposal(isolated_database: str) -> None:
    _prepare_data(isolated_database)
    app = _build_app()

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("p")
        await pilot.pause()
        assert isinstance(app.screen, ProposalsScreen)

        table = app.screen.query_one("#proposals-table", DataTable)
        assert table.row_count == 1
        assert str(table.ordered_columns[2].label) == "Título"
        assert table.get_row_at(0)[2] == "Proposta TUI"
        assert table.get_row_at(0)[3] == "Rascunho"

        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, ProposalScreen)

        sections = app.screen.query_one("#section-table", DataTable)
        assert sections.row_count == 9
        assert str(sections.ordered_columns[3].label) == "Caracteres"
        row = sections.get_row_at(0)
        assert row[0] == "resumo"
        assert row[2] == "Vazia"

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ProposalsScreen)


# Cria uma área de trabalho pelo modal da tela inicial.
@pytest.mark.asyncio
async def test_tui_creates_workspace(isolated_database: str) -> None:
    _prepare_data(isolated_database)
    app = _build_app()

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        app.screen.query_one("#workspace-name", Input).value = "Nova área"
        app.screen.query_one(
            "#workspace-description",
            Input,
        ).value = "Criada pela TUI"
        await pilot.click("#save", offset=(1, 1))
        await pilot.pause()

        assert isinstance(app.screen, HomeScreen)
        table = app.screen.query_one("#home-workspaces-table", DataTable)
        assert table.row_count == 2


# Cria e edita o perfil local pela TUI.
@pytest.mark.asyncio
async def test_tui_creates_and_edits_profile(isolated_database: str) -> None:
    _prepare_data(isolated_database)
    app = _build_app()

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("u")
        await pilot.pause()
        assert isinstance(app.screen, ProfileScreen)

        await pilot.click("#init", offset=(1, 1))
        await pilot.pause()
        assert "Perfil padrão" in str(
            app.screen.query_one("#profile-status").content
        )

        await pilot.click("#edit", offset=(1, 1))
        await pilot.pause()
        assert isinstance(app.screen, ProfileEditScreen)
        app.screen.query_one("#profile-full_name", Input).value = "Fulano de Tal"
        await pilot.click("#save", offset=(1, 1))
        await pilot.pause()

        assert isinstance(app.screen, ProfileScreen)
        content = str(app.screen.query_one("#profile-content").content)
        assert "Fulano de Tal" in content


# Adiciona e lista uma fonte PDF pela TUI.
@pytest.mark.asyncio
async def test_tui_adds_local_source(isolated_database: str) -> None:
    _prepare_data(isolated_database)
    app = _build_app()

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        tabs = app.screen.query_one("#workspace-tabs", TabbedContent)
        tabs.active = "tab-sources"
        await pilot.pause()

        sources = app.screen.query_one(SourcesPane)
        await sources._after_add_file(str(FIXTURES / "sample_edital.pdf"))
        await pilot.pause()

        table = sources.query_one("#sources-table", DataTable)
        assert table.row_count == 1
        assert table.get_row_at(0)[2] == "PDF local"
        assert table.get_row_at(0)[3] == "Pronta"


# Envia uma pergunta usando um agente simulado.
@pytest.mark.asyncio
async def test_tui_chat_sends_question(
    isolated_database: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id, _ = _prepare_data(isolated_database)
    app = _build_app()

    def fake_ask(
        _workspace_id: int,
        _question: str,
        *,
        top_k: int | None = None,
        history: object = None,
    ) -> ChatAnswer:
        assert _workspace_id == workspace_id
        assert top_k is None
        return ChatAnswer(answer="Resposta simulada", model="modelo-teste")

    monkeypatch.setattr(app.services.chat, "ask", fake_ask)

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        tabs = app.screen.query_one("#workspace-tabs", TabbedContent)
        tabs.active = "tab-chat"
        await pilot.pause()

        chat = app.screen.query_one(ChatPane)
        chat.query_one("#chat-input", Input).value = "Qual é o prazo?"
        await pilot.click("#chat-send", offset=(1, 1))
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert len(chat.history) == 2
        assert chat.history[0].content == "Qual é o prazo?"
        assert chat.history[1].content == "Resposta simulada"


# Executa o diagnóstico com verificações simuladas.
@pytest.mark.asyncio
async def test_tui_runs_doctor(
    isolated_database: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare_data(isolated_database)
    app = _build_app()

    monkeypatch.setattr(
        app.services.diagnostics,
        "run",
        lambda: [DiagnosticCheck(name="teste", ok=True, detail="tudo certo")],
    )

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("t")
        await pilot.pause()
        assert isinstance(app.screen, ToolsScreen)

        await pilot.click("#doctor-run", offset=(1, 1))
        await app.workers.wait_for_complete()
        await pilot.pause()

        status = str(app.screen.query_one("#doctor-status").content)
        assert "sem falhas" in status


# Cria uma proposta pelo modal da lista global.
@pytest.mark.asyncio
async def test_tui_creates_proposal(isolated_database: str) -> None:
    _prepare_data(isolated_database)
    app = _build_app()

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("p")
        await pilot.pause()

        await pilot.press("n")
        await pilot.pause()
        app.screen.query_one("#proposal-title", Input).value = "Nova proposta TUI"
        await pilot.click("#save", offset=(1, 1))
        await pilot.pause()

        assert isinstance(app.screen, ProposalScreen)
        assert "Nova proposta TUI" in str(
            app.screen.query_one("#proposal-title").content
        )

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ProposalsScreen)
        table = app.screen.query_one("#proposals-table", DataTable)
        assert table.row_count == 2
        titles = [table.get_row_at(index)[2] for index in range(table.row_count)]
        assert "Nova proposta TUI" in titles


# Inspeciona uma URL usando um resultado simulado.
@pytest.mark.asyncio
async def test_tui_inspects_form(
    isolated_database: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare_data(isolated_database)
    app = _build_app()

    result = DetectionResult(
        page=PageSnapshot(url="https://example.test/form", title="Formulário"),
    )
    monkeypatch.setattr(
        app.services.inspection,
        "inspect_sync",
        lambda _url: result,
    )

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("t")
        await pilot.pause()
        tabs = app.screen.query_one("#tools-tabs", TabbedContent)
        tabs.active = "tab-inspect"
        await pilot.pause()

        app.screen.query_one("#inspect-url", Input).value = "https://example.test/form"
        await pilot.click("#inspect-run", offset=(1, 1))
        await app.workers.wait_for_complete()
        await pilot.pause()

        status = str(app.screen.query_one("#inspect-status").content)
        assert "Inspeção concluída" in status
