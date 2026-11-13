# Telas de listagem e leitura de propostas.

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Button, DataTable, Footer, Header, Static

from app.schemas.proposal import ProposalDetail, ProposalSection
from app.tui.labels import (
    PROPOSAL_STATUS_LABELS,
    SECTION_STATUS_LABELS,
    label_for,
)
from app.tui.services import TuiServices
from app.tui.widgets.modals import ProposalCreateModal


# Tela de leitura de uma proposta e seu sumário de seções.
class ProposalScreen(Screen):
    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "back", "Voltar"),
        ("r", "reload", "Atualizar"),
    ]

    def __init__(self, services: TuiServices, proposal_id: int) -> None:
        super().__init__()
        self.services = services
        self.proposal_id = proposal_id
        self._proposal: ProposalDetail | None = None
        self._sections: dict[int, ProposalSection] = {}
        self._table_ready = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(classes="screen-body"):
            yield Static("", id="proposal-title", classes="title")
            yield Static("", id="proposal-meta", classes="hint")
            yield DataTable(id="section-table", classes="table")
            yield Static(
                "Selecione uma seção para ver o conteúdo.",
                id="section-preview",
                classes="detail-box",
            )
            with Horizontal(classes="actions"):
                yield Button("Voltar", id="back")
                yield Button("Atualizar", id="refresh")
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
            proposal = self.services.proposals.get(self.proposal_id)
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Erro ao carregar proposta: {exc}", severity="error")
            return

        self._proposal = proposal
        self._sections = {section.id: section for section in proposal.sections}
        self.query_one("#proposal-title", Static).update(proposal.title)
        self.query_one("#proposal-meta", Static).update(
            f"ID {proposal.id} — área de trabalho {proposal.workspace_id} — "
            f"situação {label_for(PROPOSAL_STATUS_LABELS, proposal.status)} — "
            f"revisão {proposal.current_revision}"
        )

        for section in proposal.sections:
            table.add_row(
                section.key,
                section.title,
                label_for(SECTION_STATUS_LABELS, section.status),
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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.action_back()
        elif event.button.id == "refresh":
            self._load_proposal()

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_reload(self) -> None:
        self._load_proposal()


# Lista global ou filtrada por área de trabalho.
class ProposalsScreen(Screen):
    BINDINGS: ClassVar[list[BindingType]] = [
        ("n", "new_proposal", "Nova"),
        ("r", "refresh", "Atualizar"),
        ("escape", "back", "Voltar"),
    ]

    def __init__(
        self,
        services: TuiServices,
        *,
        workspace_id: int | None = None,
    ) -> None:
        super().__init__()
        self.services = services
        self.workspace_id = workspace_id
        self._table_ready = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(classes="screen-body"):
            title = "Propostas"
            if self.workspace_id is not None:
                title = "Propostas da área de trabalho"
            yield Static(title, classes="title")
            yield DataTable(id="proposals-table", classes="table")
            with Horizontal(classes="actions"):
                yield Button("Nova proposta", id="new", variant="primary")
                yield Button("Abrir", id="open")
                yield Button("Atualizar", id="refresh")
                yield Button("Voltar", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._load()
        self.query_one("#proposals-table", DataTable).focus()

    def _load(self) -> None:
        table = self.query_one("#proposals-table", DataTable)
        table.cursor_type = "row"
        if not self._table_ready:
            table.add_columns("ID", "Área", "Título", "Situação")
            self._table_ready = True
        table.clear(columns=False)

        try:
            if self.workspace_id is None:
                proposals = self.services.proposals.list_all()
            else:
                proposals = self.services.proposals.list_by_workspace(
                    self.workspace_id
                )
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Erro ao carregar propostas: {exc}", severity="error")
            return

        for proposal in proposals:
            table.add_row(
                str(proposal.id),
                str(proposal.workspace_id),
                proposal.title,
                label_for(PROPOSAL_STATUS_LABELS, proposal.status),
                key=str(proposal.id),
            )

    def _selected_id(self) -> int | None:
        table = self.query_one("#proposals-table", DataTable)
        if table.row_count == 0:
            return None
        row = table.get_row_at(table.cursor_coordinate.row)
        return int(row[0])

    def _open_selected(self) -> None:
        proposal_id = self._selected_id()
        if proposal_id is None:
            self.notify("Selecione uma proposta.", severity="warning")
            return
        self.app.push_screen(ProposalScreen(self.services, proposal_id))

    def action_new_proposal(self) -> None:
        try:
            workspaces = self.services.workspaces.list_all()
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Erro ao carregar áreas de trabalho: {exc}", severity="error")
            return

        if not workspaces:
            self.notify(
                "Crie uma área de trabalho antes de criar uma proposta.",
                severity="warning",
            )
            return

        self.app.push_screen(
            ProposalCreateModal(workspaces, self.workspace_id),
            self._after_create,
        )

    async def _after_create(self, result: object) -> None:
        if not isinstance(result, tuple) or len(result) != 3:
            return
        workspace_id, title, description = result
        try:
            proposal = self.services.proposals.create(
                int(workspace_id),
                str(title),
                str(description),
            )
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Erro ao criar proposta: {exc}", severity="error")
            return

        self._load()
        self.notify(f"Proposta {proposal.id} criada.", severity="information")
        self.app.push_screen(ProposalScreen(self.services, proposal.id))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "new":
                self.action_new_proposal()
            case "open":
                self._open_selected()
            case "refresh":
                self._load()
            case "back":
                self.action_back()

    def on_data_table_row_selected(
        self,
        _event: DataTable.RowSelected,
    ) -> None:
        self._open_selected()

    def action_refresh(self) -> None:
        self._load()

    def action_back(self) -> None:
        self.app.pop_screen()


# Painel de propostas dentro de uma área de trabalho.
class ProposalsPane(Widget):
    BINDINGS: ClassVar[list[BindingType]] = [
        ("n", "new_proposal", "Nova"),
        ("r", "refresh", "Atualizar"),
    ]

    def __init__(self, services: TuiServices, workspace_id: int) -> None:
        super().__init__()
        self.services = services
        self.workspace_id = workspace_id
        self._table_ready = False

    def compose(self) -> ComposeResult:
        with Vertical(classes="pane-body"):
            yield Static("Propostas", classes="section-title")
            yield DataTable(id="workspace-proposals-table", classes="table")
            with Horizontal(classes="actions"):
                yield Button("Nova proposta", id="new", variant="primary")
                yield Button("Abrir", id="open")
                yield Button("Atualizar", id="refresh")

    def on_mount(self) -> None:
        self._load()

    def _load(self) -> None:
        table = self.query_one("#workspace-proposals-table", DataTable)
        table.cursor_type = "row"
        if not self._table_ready:
            table.add_columns("ID", "Título", "Situação", "Revisão")
            self._table_ready = True
        table.clear(columns=False)

        try:
            proposals = self.services.proposals.list_by_workspace(self.workspace_id)
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Erro ao carregar propostas: {exc}", severity="error")
            return

        for proposal in proposals:
            table.add_row(
                str(proposal.id),
                proposal.title,
                label_for(PROPOSAL_STATUS_LABELS, proposal.status),
                str(proposal.current_revision),
                key=str(proposal.id),
            )

    def _selected_id(self) -> int | None:
        table = self.query_one("#workspace-proposals-table", DataTable)
        if table.row_count == 0:
            return None
        row = table.get_row_at(table.cursor_coordinate.row)
        return int(row[0])

    def _open_selected(self) -> None:
        proposal_id = self._selected_id()
        if proposal_id is None:
            self.notify("Selecione uma proposta.", severity="warning")
            return
        self.app.push_screen(ProposalScreen(self.services, proposal_id))

    def action_new_proposal(self) -> None:
        try:
            workspaces = self.services.workspaces.list_all()
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Erro ao carregar áreas de trabalho: {exc}", severity="error")
            return

        self.app.push_screen(
            ProposalCreateModal(workspaces, self.workspace_id),
            self._after_create,
        )

    async def _after_create(self, result: object) -> None:
        if not isinstance(result, tuple) or len(result) != 3:
            return
        workspace_id, title, description = result
        try:
            proposal = self.services.proposals.create(
                int(workspace_id),
                str(title),
                str(description),
            )
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Erro ao criar proposta: {exc}", severity="error")
            return

        self._load()
        self.notify(f"Proposta {proposal.id} criada.", severity="information")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "new":
                self.action_new_proposal()
            case "open":
                self._open_selected()
            case "refresh":
                self._load()

    def on_data_table_row_selected(
        self,
        _event: DataTable.RowSelected,
    ) -> None:
        self._open_selected()

    def action_refresh(self) -> None:
        self._load()
