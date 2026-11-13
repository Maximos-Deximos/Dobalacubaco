# Testes da tela de revisão de PDF em tempo real.

import pytest
from textual.widgets import DataTable, Input, Static

from app.memory.database import init_db
from app.tui.app import ProposalTuiApp
from app.tui.screens.pdf_form import PdfFormScreen
from app.tui.screens.sources import SourceDetailScreen
from app.tui.services import build_services
from tests.pdf_helpers import FakePdfClient, create_pdf_source


# Monta a tela e verifica o autosave de edição manual.
@pytest.mark.asyncio
async def test_pdf_screen_autosaves_inline_edit(isolated_database: str) -> None:
    init_db(isolated_database)
    _workspace_id, source = create_pdf_source()
    services = build_services()
    app = ProposalTuiApp(services)

    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        app.push_screen(PdfFormScreen(services, source.id))
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, PdfFormScreen)
        assert screen.session is not None
        table = screen.query_one("#pdf-fields-table", DataTable)
        assert table.row_count == 5

        field_input = screen.query_one("#pdf-field-input", Input)
        field_input.value = "Nome Editado"
        await pilot.pause(0.6)

        detail = services.pdf_forms.get_session(screen.session.id)
        field = next(item for item in detail.fields if item.field_name == "full_name")
        assert field.final_value == "Nome Editado"
        assert field.status.value == "edited"
        assert table.get_row_at(0)[3] == "Nome Editado"


# Abre a tela de PDF pelo detalhe da fonte.
@pytest.mark.asyncio
async def test_source_detail_opens_pdf_screen(isolated_database: str) -> None:
    init_db(isolated_database)
    _workspace_id, source = create_pdf_source()
    services = build_services()
    app = ProposalTuiApp(services)

    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        app.push_screen(SourceDetailScreen(services, source.id))
        await pilot.pause()

        detail = app.screen
        assert isinstance(detail, SourceDetailScreen)
        assert detail.query_one("#pdf-form").disabled is False

        await pilot.press("p")
        await pilot.pause()
        assert isinstance(app.screen, PdfFormScreen)


# Executa a geração progressiva e mantém o status de sugestão.
@pytest.mark.asyncio
async def test_pdf_screen_progressive_suggestions(isolated_database: str) -> None:
    init_db(isolated_database)
    _workspace_id, source = create_pdf_source()
    services = build_services()
    fake_client = FakePdfClient()
    services.pdf_forms.client = fake_client
    services.pdf_forms.embedder = fake_client
    services.pdf_forms.retriever.embedder = fake_client
    app = ProposalTuiApp(services)

    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        app.push_screen(PdfFormScreen(services, source.id))
        await pilot.pause()

        screen = app.screen
        await pilot.press("s")
        await pilot.pause(1.5)

        assert screen._busy is False
        table = screen.query_one("#pdf-fields-table", DataTable)
        assert table.get_row_at(0)[3] == "Fulano de Tal"
        assert table.get_row_at(0)[5] == "Sugerido"
        assert table.get_row_at(1)[3] == "fulano@example.com"
        status = screen.query_one("#pdf-form-status", Static)
        assert "Revisão pronta" in str(status.content)

        detail = services.pdf_forms.get_session(screen.session.id)
        assert all(field.status.value == "suggested" for field in detail.fields)


# Aprova todos os campos e preenche pela tela.
@pytest.mark.asyncio
async def test_pdf_screen_approves_and_fills(
    isolated_database: str,
    tmp_path,
) -> None:
    init_db(isolated_database)
    _workspace_id, source = create_pdf_source()
    services = build_services()
    fake_client = FakePdfClient()
    services.pdf_forms.client = fake_client
    services.pdf_forms.embedder = fake_client
    services.pdf_forms.retriever.embedder = fake_client
    app = ProposalTuiApp(services)

    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        screen = PdfFormScreen(services, source.id)
        app.push_screen(screen)
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause(1.5)

        await pilot.press("a")
        await pilot.pause(0.8)
        detail = services.pdf_forms.get_session(screen.session.id)
        assert all(field.status.value == "approved" for field in detail.fields)

        output = tmp_path / "tui.pdf"
        await screen._start_fill(output)
        await pilot.pause(0.5)
        assert output.is_file()
        assert "PDF preenchido" in str(
            screen.query_one("#pdf-form-status", Static).content
        )
