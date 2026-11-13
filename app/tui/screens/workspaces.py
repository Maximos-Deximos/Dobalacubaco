# Telas de listagem e detalhe de áreas de trabalho.

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Static,
    TabbedContent,
    TabPane,
)

from app.schemas.workspace import Workspace
from app.tui.labels import WORKSPACE_STATUS_LABELS, label_for
from app.tui.screens.chat import ChatPane
from app.tui.screens.proposals import ProposalsPane
from app.tui.screens.sources import SourcesPane
from app.tui.services import TuiServices
from app.tui.widgets.modals import WorkspaceCreateModal


# Lista completa de áreas de trabalho.
class WorkspacesScreen(Screen):
    BINDINGS: ClassVar[list[BindingType]] = [
        ("n", "new_workspace", "Nova"),
        ("r", "refresh", "Atualizar"),
        ("escape", "back", "Voltar"),
    ]

    def __init__(self, services: TuiServices) -> None:
        super().__init__()
        self.services = services
        self._table_ready = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(classes="screen-body"):
            yield Static("Áreas de trabalho", classes="title")
            yield DataTable(id="workspaces-table", classes="table")
            with Horizontal(classes="actions"):
                yield Button("Nova área", id="new", variant="primary")
                yield Button("Abrir", id="open")
                yield Button("Atualizar", id="refresh")
                yield Button("Voltar", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._load()
        self.query_one("#workspaces-table", DataTable).focus()

    def _load(self) -> None:
        table = self.query_one("#workspaces-table", DataTable)
        table.cursor_type = "row"
        if not self._table_ready:
            table.add_columns("ID", "Nome", "Situação", "Descrição")
            self._table_ready = True
        table.clear(columns=False)

        try:
            workspaces = self.services.workspaces.list_all()
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Erro ao carregar áreas de trabalho: {exc}", severity="error")
            return

        for workspace in workspaces:
            table.add_row(
                str(workspace.id),
                workspace.name,
                label_for(WORKSPACE_STATUS_LABELS, workspace.status),
                workspace.description,
                key=str(workspace.id),
            )

    def _selected_workspace_id(self) -> int | None:
        table = self.query_one("#workspaces-table", DataTable)
        if table.row_count == 0:
            return None
        row = table.get_row_at(table.cursor_coordinate.row)
        return int(row[0])

    def _open_selected(self) -> None:
        workspace_id = self._selected_workspace_id()
        if workspace_id is None:
            self.notify("Selecione uma área de trabalho.", severity="warning")
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


# Detalhe de uma área de trabalho com fontes, conversa e propostas.
class WorkspaceScreen(Screen):
    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "back", "Voltar"),
        ("r", "reload", "Atualizar"),
    ]

    def __init__(self, services: TuiServices, workspace_id: int) -> None:
        super().__init__()
        self.services = services
        self.workspace_id = workspace_id
        try:
            self._workspace: Workspace | None = self.services.workspaces.get(
                workspace_id
            )
        except Exception:  # noqa: BLE001
            self._workspace = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(classes="screen-body"):
            yield Static("", id="workspace-title", classes="title")
            yield Static("", id="workspace-meta", classes="hint")
            with TabbedContent(initial="tab-overview", id="workspace-tabs"):
                with TabPane("Visão geral", id="tab-overview"):
                    yield Static("", id="workspace-overview", classes="detail-box")
                with TabPane("Fontes", id="tab-sources"):
                    yield SourcesPane(
                        self.services,
                        self.workspace_id,
                        self._workspace_name(),
                    )
                with TabPane("Conversa", id="tab-chat"):
                    yield ChatPane(
                        self.services,
                        self.workspace_id,
                        self._workspace_name(),
                    )
                with TabPane("Propostas", id="tab-proposals"):
                    yield ProposalsPane(self.services, self.workspace_id)
            with Horizontal(classes="actions"):
                yield Button("Voltar", id="back")
                yield Button("Atualizar", id="refresh")
        yield Footer()

    def on_mount(self) -> None:
        self._load_workspace()

    def on_tabbed_content_tab_activated(
        self,
        event: TabbedContent.TabActivated,
    ) -> None:
        match event.pane.id:
            case "tab-sources":
                self.query_one(SourcesPane).query_one("#sources-table").focus()
            case "tab-chat":
                self.query_one(ChatPane).query_one("#chat-input").focus()
            case "tab-proposals":
                self.query_one(ProposalsPane).query_one(
                    "#workspace-proposals-table"
                ).focus()

    def _workspace_name(self) -> str:
        return self._workspace.name if self._workspace is not None else "Área de trabalho"

    def _load_workspace(self) -> None:
        try:
            workspace = self.services.workspaces.get(self.workspace_id)
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Erro ao carregar área de trabalho: {exc}", severity="error")
            return

        self._workspace = workspace
        self.query_one("#workspace-title", Static).update(workspace.name)
        self.query_one("#workspace-meta", Static).update(
            f"ID {workspace.id} — situação "
            f"{label_for(WORKSPACE_STATUS_LABELS, workspace.status)}"
        )
        self.query_one("#workspace-overview", Static).update(
            _format_workspace_overview(self.services, workspace)
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.action_back()
        elif event.button.id == "refresh":
            self.action_reload()

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_reload(self) -> None:
        self._load_workspace()


# Monta o resumo exibido na aba de visão geral.
def _format_workspace_overview(services: TuiServices, workspace: Workspace) -> str:
    lines = [
        f"Área de trabalho: {workspace.name}",
        f"ID: {workspace.id}",
        f"Situação: {label_for(WORKSPACE_STATUS_LABELS, workspace.status)}",
        f"Descrição: {workspace.description or '(sem descrição)'}",
        f"Criada em: {workspace.created_at.isoformat()}",
        f"Atualizada em: {workspace.updated_at.isoformat()}",
        "",
    ]

    try:
        sources = services.sources.list_sources(workspace.id)
        proposals = services.proposals.list_by_workspace(workspace.id)
        status = services.chat.status(workspace.id)
    except Exception as exc:  # noqa: BLE001
        lines.append(f"Não foi possível carregar os totais: {exc}")
        return "\n".join(lines)

    lines.extend(
        [
            f"Fontes: {len(sources)} (prontas: {status.sources_ready})",
            (
                f"Trechos indexados: {status.chunks_total} "
                f"(com embeddings: {status.chunks_embedded})"
            ),
            f"Propostas: {len(proposals)}",
        ]
    )
    return "\n".join(lines)
