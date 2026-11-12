# Aplicação Textual para navegação local de propostas.

from __future__ import annotations

import sys
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Markdown,
    Static,
)

from app.application.proposal_service import ProposalService
from app.memory.database import init_db
from app.schemas.proposal import ProposalDetail, ProposalSection
from app.ui.help import render_global_help

PROPOSAL_STATUS_LABELS = {
    "draft": "Rascunho",
    "in_review": "Em revisão",
    "completed": "Concluída",
    "archived": "Arquivada",
}

SECTION_STATUS_LABELS = {
    "empty": "Vazia",
    "draft": "Rascunho",
    "in_review": "Em revisão",
    "approved": "Aprovada",
}

CSS = """
Screen {
    layout: vertical;
}

#home-body, #proposal-body {
    height: 1fr;
    padding: 1 2;
}

#home-title, #proposal-title {
    text-style: bold;
    padding-bottom: 1;
}

#create-row {
    height: auto;
    margin-bottom: 1;
}

#create-row Input {
    width: 1fr;
    margin-right: 1;
}

#proposal-table, #section-table {
    height: 1fr;
    min-height: 8;
}

#actions {
    height: auto;
    margin-top: 1;
}

#actions Button {
    margin-right: 1;
}

#section-preview {
    height: auto;
    max-height: 12;
    border: round $primary;
    padding: 0 1;
    margin-top: 1;
}

#help-body {
    height: 1fr;
    padding: 1 2;
}
"""


# Traduz um status armazenado para o rótulo exibido na TUI.
def _status_label(labels: dict[str, str], value: object) -> str:
    key = str(getattr(value, "value", value))
    return labels.get(key, key)


# Tela inicial com criação e navegação de propostas.
class HomeScreen(Screen):
    BINDINGS: ClassVar[list[BindingType]] = [
        ("r", "refresh", "Atualizar"),
        ("n", "focus_new", "Nova"),
    ]

    def __init__(self, service: ProposalService) -> None:
        super().__init__()
        self.service = service
        self._table_ready = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="home-body"):
            yield Static("Propostas de solução", id="home-title")
            with Horizontal(id="create-row"):
                yield Input(
                    placeholder="ID da área de trabalho",
                    id="workspace-id",
                )
                yield Input(
                    placeholder="Título da nova proposta",
                    id="proposal-title",
                )
                yield Button("Criar", id="create", variant="primary")
            yield DataTable(id="proposal-table")
            with Horizontal(id="actions"):
                yield Button("Abrir", id="open")
                yield Button("Ajuda", id="help")
                yield Button("Atualizar", id="refresh")
        yield Footer()

    def on_mount(self) -> None:
        self._load_proposals()
        self.query_one("#proposal-table", DataTable).focus()

    # Carrega ou recarrega a lista de propostas.
    def _load_proposals(self) -> None:
        table = self.query_one("#proposal-table", DataTable)
        table.cursor_type = "row"
        if not self._table_ready:
            table.add_columns("ID", "Área", "Título", "Situação")
            self._table_ready = True
        table.clear(columns=False)

        try:
            proposals = self.service.list_all()
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Erro ao carregar propostas: {exc}", severity="error")
            return

        for proposal in proposals:
            table.add_row(
                str(proposal.id),
                str(proposal.workspace_id),
                proposal.title,
                _status_label(PROPOSAL_STATUS_LABELS, proposal.status),
                key=str(proposal.id),
            )

    # Devolve o ID da proposta selecionada, se houver.
    def _selected_proposal_id(self) -> int | None:
        table = self.query_one("#proposal-table", DataTable)
        if table.row_count == 0:
            return None
        row = table.get_row_at(table.cursor_coordinate.row)
        return int(row[0])

    # Abre a proposta selecionada.
    def _open_selected(self) -> None:
        proposal_id = self._selected_proposal_id()
        if proposal_id is None:
            self.notify("Selecione uma proposta.", severity="warning")
            return
        self.app.push_screen(ProposalScreen(self.service, proposal_id))

    # Cria uma proposta com os dados informados.
    def _create_proposal(self) -> None:
        workspace_raw = self.query_one("#workspace-id", Input).value.strip()
        title = self.query_one("#proposal-title", Input).value.strip()

        if not workspace_raw or not title:
            self.notify(
                "Informe o ID da área de trabalho e o título.",
                severity="warning",
            )
            return

        try:
            workspace_id = int(workspace_raw)
        except ValueError:
            self.notify("O ID da área de trabalho deve ser numérico.", severity="error")
            return

        try:
            proposal = self.service.create(workspace_id, title)
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Erro ao criar proposta: {exc}", severity="error")
            return

        self.query_one("#proposal-title", Input).value = ""
        self._load_proposals()
        self.notify(f"Proposta {proposal.id} criada.", severity="information")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "create":
                self._create_proposal()
            case "open":
                self._open_selected()
            case "help":
                self.app.action_help()
            case "refresh":
                self._load_proposals()

    def on_data_table_row_selected(
        self,
        _event: DataTable.RowSelected,
    ) -> None:
        self._open_selected()

    def action_refresh(self) -> None:
        self._load_proposals()

    def action_focus_new(self) -> None:
        self.query_one("#workspace-id", Input).focus()


# Tela de leitura de uma proposta e seu sumário de seções.
class ProposalScreen(Screen):
    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "back", "Voltar"),
        ("r", "reload", "Atualizar"),
    ]

    def __init__(self, service: ProposalService, proposal_id: int) -> None:
        super().__init__()
        self.service = service
        self.proposal_id = proposal_id
        self._proposal: ProposalDetail | None = None
        self._sections: dict[int, ProposalSection] = {}
        self._table_ready = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="proposal-body"):
            yield Static("", id="proposal-title")
            yield DataTable(id="section-table")
            yield Static("Selecione uma seção.", id="section-preview")
        yield Footer()

    def on_mount(self) -> None:
        self._load_proposal()
        self.query_one("#section-table", DataTable).focus()

    # Carrega ou recarrega a proposta atual.
    def _load_proposal(self) -> None:
        table = self.query_one("#section-table", DataTable)
        table.cursor_type = "row"
        if not self._table_ready:
            table.add_columns("Chave", "Título", "Situação", "Caracteres")
            self._table_ready = True
        table.clear(columns=False)

        try:
            proposal = self.service.get(self.proposal_id)
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Erro ao carregar proposta: {exc}", severity="error")
            return

        self._proposal = proposal
        self._sections = {section.id: section for section in proposal.sections}
        title = self.query_one("#proposal-title", Static)
        title.update(
            f"{proposal.title} (id={proposal.id}) — "
            f"área de trabalho {proposal.workspace_id} — revisão {proposal.current_revision}"
        )

        for section in proposal.sections:
            table.add_row(
                section.key,
                section.title,
                _status_label(SECTION_STATUS_LABELS, section.status),
                str(len(section.content)),
                key=str(section.id),
            )

    def on_data_table_row_selected(
        self,
        event: DataTable.RowSelected,
    ) -> None:
        section_id = int(str(event.row_key.value))
        section = self._sections.get(section_id)
        preview = self.query_one("#section-preview", Static)
        if section is None:
            preview.update("Seção não encontrada.")
            return
        content = section.content.strip() or "(seção ainda vazia)"
        preview.update(f"{section.title}\n\n{content}")

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_reload(self) -> None:
        self._load_proposal()


# Tela de ajuda compartilhando o registro central da CLI.
class HelpScreen(Screen):
    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "back", "Voltar")
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with VerticalScroll(id="help-body"):
            yield Markdown(render_global_help())
        yield Footer()

    def action_back(self) -> None:
        self.app.pop_screen()


# Aplicação principal da interface de terminal.
class ProposalTuiApp(App):
    TITLE = "Agente de Editais"
    CSS = CSS
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit", "Sair"),
        Binding("question_mark", "help", "Ajuda", priority=True),
        Binding("f1", "help", "Ajuda", priority=True),
    ]

    def __init__(self, service: ProposalService | None = None) -> None:
        super().__init__()
        self.service = service or ProposalService()

    def on_mount(self) -> None:
        self.push_screen(HomeScreen(self.service))

    def action_help(self) -> None:
        if isinstance(self.screen, HelpScreen):
            return
        self.push_screen(HelpScreen())


# Abre a interface de terminal, exigindo um TTY interativo.
def run_tui() -> int:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print(
            "A TUI requer um terminal interativo. "
            "Use 'python -m app.main help' para ver os comandos.",
            file=sys.stderr,
        )
        return 1

    try:
        init_db()
    except Exception as exc:  # noqa: BLE001
        print(f"Erro ao inicializar o banco: {exc}", file=sys.stderr)
        return 1

    ProposalTuiApp().run()
    return 0
