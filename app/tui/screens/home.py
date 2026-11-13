# Tela inicial com o painel geral do agente.

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Static

from app.tui.labels import WORKSPACE_STATUS_LABELS, label_for
from app.tui.screens.help import HelpScreen
from app.tui.screens.profile import ProfileScreen
from app.tui.screens.proposals import ProposalsScreen
from app.tui.screens.tools import ToolsScreen
from app.tui.screens.workspaces import WorkspaceScreen, WorkspacesScreen
from app.tui.services import TuiServices
from app.tui.widgets.modals import WorkspaceCreateModal


# Painel inicial com totais e acesso rápido às áreas de trabalho.
class HomeScreen(Screen):
    BINDINGS: ClassVar[list[BindingType]] = [
        ("n", "new_workspace", "Nova área"),
        ("w", "workspaces", "Áreas"),
        ("p", "proposals", "Propostas"),
        ("t", "tools", "Ferramentas"),
        ("u", "profile", "Perfil"),
        ("r", "refresh", "Atualizar"),
    ]

    def __init__(self, services: TuiServices) -> None:
        super().__init__()
        self.services = services
        self._table_ready = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(classes="screen-body"):
            yield Static("Agente de Editais", classes="title")
            yield Static(
                "Gerencie áreas de trabalho, fontes e propostas de solução.",
                classes="hint",
            )
            yield Static("", id="home-stats", classes="detail-box")
            yield Static("Áreas de trabalho recentes", classes="section-title")
            yield DataTable(id="home-workspaces-table", classes="table")
            with Horizontal(classes="actions"):
                yield Button("Nova área", id="new", variant="primary")
                yield Button("Áreas", id="workspaces")
                yield Button("Propostas", id="proposals")
                yield Button("Ferramentas", id="tools")
                yield Button("Perfil", id="profile")
                yield Button("Ajuda", id="help")
                yield Button("Atualizar", id="refresh")
                yield Button("Sair", id="quit")
        yield Footer()

    def on_mount(self) -> None:
        self._load()
        self.query_one("#home-workspaces-table", DataTable).focus()

    def _load(self) -> None:
        table = self.query_one("#home-workspaces-table", DataTable)
        table.cursor_type = "row"
        if not self._table_ready:
            table.add_columns("ID", "Nome", "Situação", "Descrição")
            self._table_ready = True
        table.clear(columns=False)

        try:
            workspaces = self.services.workspaces.list_all()
            proposals = self.services.proposals.list_all()
            profile = self.services.users.get_default()
        except Exception as exc:  # noqa: BLE001
            self.query_one("#home-stats", Static).update(
                f"Erro ao carregar o painel: {exc}"
            )
            return

        sources_total = 0
        sources_ready = 0
        for workspace in workspaces:
            try:
                sources = self.services.sources.list_sources(workspace.id)
            except Exception:  # noqa: BLE001
                sources = []
            sources_total += len(sources)
            sources_ready += sum(1 for source in sources if source.status == "ready")

        profile_label = profile.name if profile is not None else "não cadastrado"
        self.query_one("#home-stats", Static).update(
            f"Áreas de trabalho: {len(workspaces)}\n"
            f"Fontes: {sources_total} (prontas: {sources_ready})\n"
            f"Propostas: {len(proposals)}\n"
            f"Perfil: {profile_label}"
        )

        for workspace in workspaces:
            table.add_row(
                str(workspace.id),
                workspace.name,
                label_for(WORKSPACE_STATUS_LABELS, workspace.status),
                workspace.description,
                key=str(workspace.id),
            )

    def _selected_workspace_id(self) -> int | None:
        table = self.query_one("#home-workspaces-table", DataTable)
        if table.row_count == 0:
            return None
        row = table.get_row_at(table.cursor_coordinate.row)
        return int(row[0])

    def _open_selected(self) -> None:
        workspace_id = self._selected_workspace_id()
        if workspace_id is None:
            self.notify("Nenhuma área de trabalho selecionada.", severity="warning")
            return
        self.app.push_screen(WorkspaceScreen(self.services, workspace_id))

    def action_new_workspace(self) -> None:
        self.app.push_screen(WorkspaceCreateModal(), self._after_create)

    async def _after_create(self, result: object) -> None:
        if not isinstance(result, tuple) or len(result) != 2:
            return
        name, description = result
        try:
            workspace = self.services.workspaces.create(str(name), str(description))
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Erro ao criar área de trabalho: {exc}", severity="error")
            return

        self._load()
        self.notify(
            f"Área de trabalho '{workspace.name}' criada.",
            severity="information",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "new":
                self.action_new_workspace()
            case "workspaces":
                self.action_workspaces()
            case "proposals":
                self.action_proposals()
            case "tools":
                self.action_tools()
            case "profile":
                self.action_profile()
            case "help":
                self.action_help()
            case "refresh":
                self.action_refresh()
            case "quit":
                self.app.exit()

    def on_data_table_row_selected(
        self,
        _event: DataTable.RowSelected,
    ) -> None:
        self._open_selected()

    def action_workspaces(self) -> None:
        self.app.push_screen(WorkspacesScreen(self.services))

    def action_proposals(self) -> None:
        self.app.push_screen(ProposalsScreen(self.services))

    def action_tools(self) -> None:
        self.app.push_screen(ToolsScreen(self.services))

    def action_profile(self) -> None:
        self.app.push_screen(ProfileScreen(self.services))

    def action_help(self) -> None:
        self.app.push_screen(HelpScreen())

    def action_refresh(self) -> None:
        self._load()
