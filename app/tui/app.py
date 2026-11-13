# Aplicação Textual do agente de editais.

from __future__ import annotations

import sys
from collections.abc import Iterable
from typing import ClassVar

from textual.app import App, SystemCommand
from textual.binding import Binding, BindingType
from textual.screen import Screen

from app.memory.database import init_db
from app.tui.screens.help import HelpScreen
from app.tui.screens.home import HomeScreen
from app.tui.services import TuiServices, build_services

CSS = """
Screen {
    layout: vertical;
}

.screen-body {
    height: 1fr;
    padding: 1 2;
}

.title {
    text-style: bold;
    padding-bottom: 1;
}

.section-title {
    text-style: bold;
    padding-top: 1;
    padding-bottom: 1;
}

.hint {
    color: $text-muted;
    padding-bottom: 1;
}

.table {
    height: 1fr;
    min-height: 8;
}

.actions {
    height: auto;
    margin-top: 1;
}

.actions Button {
    margin-right: 1;
}

.detail-box {
    height: auto;
    max-height: 14;
    border: round $primary;
    padding: 0 1;
    margin-top: 1;
    overflow-y: auto;
}

.pane-body {
    height: 1fr;
    padding: 1 2;
}

TabbedContent {
    height: 1fr;
}

TabPane {
    height: 1fr;
    padding: 0;
}

.chat-controls {
    height: auto;
    margin-top: 1;
}

.chat-controls Input {
    width: 1fr;
    margin-right: 1;
}

.chat-controls .small-input {
    width: 8;
}

.chat-controls Button {
    margin-right: 1;
}

.chat-log, .tools-log {
    height: 1fr;
    min-height: 8;
    border: round $primary;
    padding: 0 1;
    margin-top: 1;
}

.profile-form {
    height: 1fr;
    border: round $primary;
    padding: 1 2;
}

.profile-form Label {
    text-style: bold;
    padding-top: 1;
}

.profile-form Input, .profile-form TextArea {
    margin-bottom: 1;
}

.modal {
    width: 70;
    height: auto;
    max-height: 90%;
    border: round $primary;
    background: $surface;
    padding: 1 2;
}

.modal-title {
    text-style: bold;
    padding-bottom: 1;
}

.modal-buttons {
    height: auto;
    margin-top: 1;
}

.modal-buttons Button {
    margin-right: 1;
}

#help-body {
    height: 1fr;
    padding: 1 2;
}

#source-content, #profile-content {
    height: 1fr;
}

.pdf-form-body {
    height: 1fr;
}

.pdf-main {
    height: 1fr;
    min-height: 10;
}

.pdf-fields-column {
    width: 1fr;
    height: 1fr;
}

.pdf-editor {
    width: 44;
    height: 1fr;
    border: round $primary;
    padding: 0 1;
    margin-left: 1;
    overflow-y: auto;
}

.pdf-editor Static {
    margin-bottom: 1;
}

.pdf-editor Input, .pdf-editor TextArea, .pdf-editor Select {
    margin-bottom: 1;
}

.pdf-editor TextArea {
    height: 6;
}

.pdf-warnings {
    height: 5;
    min-height: 3;
    border: round $warning;
    padding: 0 1;
    margin-top: 1;
}

#pdf-form-progress {
    height: 1;
    margin-bottom: 1;
}
"""


# Aplicação principal da interface de terminal.
class ProposalTuiApp(App):
    TITLE = "Agente de Editais"
    CSS = CSS
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit", "Sair"),
        Binding("ctrl+q", "quit", "Sair", priority=True),
        Binding("question_mark", "help", "Ajuda", priority=True),
        Binding("f1", "help", "Ajuda", priority=True),
    ]

    def __init__(self, services: TuiServices | None = None) -> None:
        super().__init__()
        self.services = services or build_services()

    def on_mount(self) -> None:
        self.push_screen(HomeScreen(self.services))

    def action_help(self) -> None:
        if isinstance(self.screen, HelpScreen):
            return
        self.push_screen(HelpScreen())

    def get_system_commands(
        self,
        screen: Screen,
    ) -> Iterable[SystemCommand]:
        yield SystemCommand(
            "Sair",
            "Encerra o aplicativo.",
            self.action_quit,
        )
        if screen.query("HelpPanel"):
            yield SystemCommand(
                "Teclas",
                "Oculta o painel de ajuda das teclas.",
                self.action_hide_help_panel,
            )
        else:
            yield SystemCommand(
                "Teclas",
                "Mostra os atalhos do campo em foco e da tela.",
                self.action_show_help_panel,
            )

    def action_help_quit(self) -> None:
        for key, active_binding in self.active_bindings.items():
            if active_binding.binding.action in ("quit", "app.quit"):
                self.notify(
                    f"Pressione [b]{key}[/b] para sair do aplicativo.",
                    title="Deseja sair?",
                )
                return


# Abre a interface de terminal, exigindo um TTY interativo.
def run_tui(services: TuiServices | None = None) -> int:
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

    ProposalTuiApp(services).run()
    return 0
