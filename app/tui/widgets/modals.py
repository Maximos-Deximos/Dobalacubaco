# Modais de criação e confirmação usados pela TUI.

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

from app.schemas.workspace import Workspace


# Janela modal com os botões padrão de salvar e cancelar.
class FormModal(ModalScreen[object]):
    BINDINGS: ClassVar[list[BindingType]] = [("escape", "cancel", "Cancelar")]

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _buttons(self) -> ComposeResult:
        with Horizontal(classes="modal-buttons"):
            yield Button("Cancelar", id="cancel")
            yield Button("Salvar", id="save", variant="primary")


# Modal para criação de uma área de trabalho.
class WorkspaceCreateModal(FormModal):
    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Static("Nova área de trabalho", classes="modal-title")
            yield Label("Nome")
            yield Input(placeholder="Ex.: Edital de inovação", id="workspace-name")
            yield Label("Descrição")
            yield Input(
                placeholder="Descrição opcional",
                id="workspace-description",
            )
            yield from self._buttons()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        if event.button.id != "save":
            return

        name = self.query_one("#workspace-name", Input).value.strip()
        description = self.query_one(
            "#workspace-description",
            Input,
        ).value.strip()
        if not name:
            self.notify("Informe o nome da área de trabalho.", severity="warning")
            return
        self.dismiss((name, description))


# Modal para ingestão de uma URL.
class SourceUrlModal(FormModal):
    def __init__(self, workspace_name: str) -> None:
        super().__init__()
        self.workspace_name = workspace_name

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Static(
                f"Adicionar URL — {self.workspace_name}",
                classes="modal-title",
            )
            yield Label("URL pública")
            yield Input(
                placeholder="https://exemplo.gov.br/edital",
                id="source-url",
            )
            yield Checkbox("Usar navegador para renderizar", id="use-browser")
            yield Checkbox("Seguir PDFs vinculados", id="follow-pdfs")
            yield Label("Máximo de PDFs vinculados")
            yield Input(
                placeholder="Deixe vazio para usar o padrão",
                id="max-links",
            )
            yield from self._buttons()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        if event.button.id != "save":
            return

        url = self.query_one("#source-url", Input).value.strip()
        if not url:
            self.notify("Informe a URL.", severity="warning")
            return

        raw_max_links = self.query_one("#max-links", Input).value.strip()
        max_links: int | None = None
        if raw_max_links:
            try:
                max_links = int(raw_max_links)
            except ValueError:
                self.notify("O limite de PDFs deve ser numérico.", severity="error")
                return
            if max_links < 0:
                self.notify("O limite de PDFs não pode ser negativo.", severity="error")
                return

        self.dismiss(
            (
                url,
                self.query_one("#use-browser", Checkbox).value,
                self.query_one("#follow-pdfs", Checkbox).value,
                max_links,
            )
        )


# Modal para ingestão de um arquivo local.
class SourceFileModal(FormModal):
    def __init__(self, workspace_name: str) -> None:
        super().__init__()
        self.workspace_name = workspace_name

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Static(
                f"Adicionar arquivo — {self.workspace_name}",
                classes="modal-title",
            )
            yield Label("Caminho do PDF ou HTML")
            yield Input(
                placeholder="/caminho/para/edital.pdf",
                id="source-path",
            )
            yield Static(
                "O arquivo precisa existir no computador local.",
                classes="hint",
            )
            yield from self._buttons()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        if event.button.id != "save":
            return

        path = self.query_one("#source-path", Input).value.strip()
        if not path:
            self.notify("Informe o caminho do arquivo.", severity="warning")
            return
        self.dismiss(path)


# Modal para criação de uma proposta.
class ProposalCreateModal(FormModal):
    def __init__(
        self,
        workspaces: list[Workspace],
        workspace_id: int | None = None,
    ) -> None:
        super().__init__()
        self.workspaces = workspaces
        self.workspace_id = workspace_id

    def compose(self) -> ComposeResult:
        options = [(workspace.name, workspace.id) for workspace in self.workspaces]
        selected = self.workspace_id
        if selected is None and options:
            selected = options[0][1]
        with Vertical(classes="modal"):
            yield Static("Nova proposta", classes="modal-title")
            yield Label("Área de trabalho")
            yield Select(
                options,
                prompt="Selecione uma área de trabalho",
                allow_blank=False,
                value=selected if selected is not None else Select.BLANK,
                id="proposal-workspace",
            )
            yield Label("Título")
            yield Input(placeholder="Título da proposta", id="proposal-title")
            yield Label("Descrição")
            yield Input(
                placeholder="Descrição opcional",
                id="proposal-description",
            )
            yield from self._buttons()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        if event.button.id != "save":
            return

        workspace_id = self.query_one("#proposal-workspace", Select).value
        title = self.query_one("#proposal-title", Input).value.strip()
        description = self.query_one(
            "#proposal-description",
            Input,
        ).value.strip()

        if workspace_id == Select.BLANK or workspace_id is None:
            self.notify("Selecione uma área de trabalho.", severity="warning")
            return
        if not title:
            self.notify("Informe o título da proposta.", severity="warning")
            return

        self.dismiss((int(workspace_id), title, description))


# Modal de confirmação com resposta booleana.
class ConfirmModal(ModalScreen[bool]):
    BINDINGS: ClassVar[list[BindingType]] = [("escape", "no", "Não")]

    def __init__(self, message: str, *, title: str = "Confirmação") -> None:
        super().__init__()
        self.message = message
        self.title_text = title

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Static(self.title_text, classes="modal-title")
            yield Static(self.message)
            with Horizontal(classes="modal-buttons"):
                yield Button("Não", id="no")
                yield Button("Sim", id="yes", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")

    def action_no(self) -> None:
        self.dismiss(False)
