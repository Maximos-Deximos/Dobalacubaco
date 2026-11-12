# Testes da interface de terminal baseada em Textual.

import pytest
from textual.widgets import DataTable, Input

from app.application.proposal_service import ProposalService
from app.application.workspace_service import WorkspaceService
from app.memory.database import init_db
from app.tui.app import HelpScreen, HomeScreen, ProposalScreen, ProposalTuiApp


# Prepara um workspace com uma proposta para os testes da TUI.
def _prepare_data(isolated_database: str) -> tuple[int, int]:
    init_db(isolated_database)
    workspace = WorkspaceService().create("Workspace TUI", "")
    proposal = ProposalService().create(workspace.id, "Proposta TUI")
    return workspace.id, proposal.id


# Exibe as propostas cadastradas na tela inicial.
@pytest.mark.asyncio
async def test_tui_home_lists_proposals(isolated_database: str) -> None:
    _prepare_data(isolated_database)
    app = ProposalTuiApp()

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, HomeScreen)
        table = app.screen.query_one("#proposal-table", DataTable)
        assert table.row_count == 1
        row = table.get_row_at(0)
        assert str(table.ordered_columns[1].label) == "Área"
        assert row[2] == "Proposta TUI"
        assert row[3] == "Rascunho"


# Abre e fecha a tela de ajuda pelo atalho.
@pytest.mark.asyncio
async def test_tui_help_shortcut(isolated_database: str) -> None:
    _prepare_data(isolated_database)
    app = ProposalTuiApp()

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("?")
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, HomeScreen)


# Abre a proposta selecionada e mostra as seções.
@pytest.mark.asyncio
async def test_tui_opens_proposal(isolated_database: str) -> None:
    _prepare_data(isolated_database)
    app = ProposalTuiApp()

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, ProposalScreen)

        table = app.screen.query_one("#section-table", DataTable)
        assert table.row_count == 9
        assert str(table.ordered_columns[3].label) == "Caracteres"
        row = table.get_row_at(0)
        assert row[0] == "resumo"
        assert row[2] == "Vazia"

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, HomeScreen)


# Cria uma proposta pelos campos da tela inicial.
@pytest.mark.asyncio
async def test_tui_creates_proposal(isolated_database: str) -> None:
    workspace_id, _ = _prepare_data(isolated_database)
    app = ProposalTuiApp()

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        home = app.screen
        home.query_one("#workspace-id", Input).value = str(workspace_id)
        home.query_one("#proposal-title", Input).value = "Nova proposta"
        home._create_proposal()
        await pilot.pause()

        table = home.query_one("#proposal-table", DataTable)
        assert table.row_count == 2
