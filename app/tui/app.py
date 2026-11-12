# Aplicação Textual do agente de editais.

from __future__ import annotations

import sys
from typing import ClassVar

from textual.app import App
from textual.binding import Binding, BindingType

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
