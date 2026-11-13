# Ferramentas de diagnóstico e inspeção de formulários.

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    RichLog,
    Static,
    TabbedContent,
    TabPane,
)

from app.schemas.form import DetectionResult
from app.tui.labels import FIELD_TYPE_LABELS, label_for
from app.tui.services import TuiServices
from app.tui.workers import run_blocking


# Tela com as ferramentas auxiliares do agente.
class ToolsScreen(Screen):
    BINDINGS: ClassVar[list[BindingType]] = [("escape", "back", "Voltar")]

    def __init__(self, services: TuiServices) -> None:
        super().__init__()
        self.services = services

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(classes="screen-body"):
            yield Static("Ferramentas", classes="title")
            with TabbedContent(initial="tab-doctor", id="tools-tabs"):
                with TabPane("Diagnóstico", id="tab-doctor"):
                    yield DoctorPane(self.services)
                with TabPane("Inspecionar formulário", id="tab-inspect"):
                    yield InspectPane(self.services)
        yield Footer()

    def on_tabbed_content_tab_activated(
        self,
        event: TabbedContent.TabActivated,
    ) -> None:
        match event.pane.id:
            case "tab-doctor":
                self.query_one("#doctor-run").focus()
            case "tab-inspect":
                self.query_one("#inspect-url").focus()

    def action_back(self) -> None:
        self.app.pop_screen()


# Executa e exibe o diagnóstico do ambiente.
class DoctorPane(Widget):
    BINDINGS: ClassVar[list[BindingType]] = [("r", "run", "Executar")]

    def __init__(self, services: TuiServices) -> None:
        super().__init__()
        self.services = services
        self._busy = False

    def compose(self) -> ComposeResult:
        with Vertical(classes="pane-body"):
            yield Static(
                "Verifica configuração, banco, Ollama e Playwright.",
                classes="hint",
            )
            yield Static("Pronto para executar.", id="doctor-status", classes="hint")
            yield RichLog(id="doctor-log", markup=False, wrap=True, classes="tools-log")
            with Horizontal(classes="actions"):
                yield Button(
                    "Executar diagnóstico",
                    id="doctor-run",
                    variant="primary",
                )
                yield Button("Limpar", id="doctor-clear")

    def _set_busy(self, busy: bool, status: str = "") -> None:
        self._busy = busy
        self.query_one("#doctor-run", Button).disabled = busy
        if status:
            self.query_one("#doctor-status", Static).update(status)

    async def _run(self) -> None:
        if self._busy:
            return

        self._set_busy(True, "Executando diagnóstico...")
        log = self.query_one("#doctor-log", RichLog)
        log.write("Executando diagnóstico do ambiente...")
        try:
            checks = await run_blocking(self, self.services.diagnostics.run)
        except Exception as exc:  # noqa: BLE001
            self._set_busy(False, "Falha no diagnóstico.")
            log.write(f"Erro: {exc}")
            self.notify(f"Erro no diagnóstico: {exc}", severity="error")
            return

        log.clear()
        for check in checks:
            marker = "OK" if check.ok else "FALHA"
            log.write(f"[{marker}] {check.name}: {check.detail}")

        failures = sum(1 for check in checks if not check.ok)
        if failures:
            self._set_busy(False, f"Diagnóstico concluído com {failures} falha(s).")
        else:
            self._set_busy(False, "Diagnóstico concluído sem falhas.")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "doctor-run":
                self.run_worker(self._run())
            case "doctor-clear":
                self.query_one("#doctor-log", RichLog).clear()
                self.query_one("#doctor-status", Static).update("Pronto para executar.")

    def action_run(self) -> None:
        self.run_worker(self._run())


# Inspeciona uma URL e lista os campos de formulário detectados.
class InspectPane(Widget):
    BINDINGS: ClassVar[list[BindingType]] = [("r", "inspect", "Inspecionar")]

    def __init__(self, services: TuiServices) -> None:
        super().__init__()
        self.services = services
        self._busy = False

    def compose(self) -> ComposeResult:
        with Vertical(classes="pane-body"):
            yield Static(
                "Informe a URL pública de um formulário para inspecionar.",
                classes="hint",
            )
            with Horizontal(classes="chat-controls"):
                yield Input(
                    placeholder="https://...",
                    id="inspect-url",
                )
                yield Button("Inspecionar", id="inspect-run", variant="primary")
            yield Static("Pronto para inspecionar.", id="inspect-status", classes="hint")
            yield RichLog(
                id="inspect-log",
                markup=False,
                wrap=True,
                classes="tools-log",
            )

    def _set_busy(self, busy: bool, status: str = "") -> None:
        self._busy = busy
        self.query_one("#inspect-run", Button).disabled = busy
        if status:
            self.query_one("#inspect-status", Static).update(status)

    async def _run(self) -> None:
        if self._busy:
            return

        url = self.query_one("#inspect-url", Input).value.strip()
        if not url:
            self.notify("Informe uma URL.", severity="warning")
            return

        log = self.query_one("#inspect-log", RichLog)
        log.clear()
        self._set_busy(True, "Abrindo a página e detectando campos...")
        try:
            result = await run_blocking(
                self,
                self.services.inspection.inspect_sync,
                url,
            )
        except Exception as exc:  # noqa: BLE001
            self._set_busy(False, "Falha na inspeção.")
            log.write(f"Erro: {exc}")
            self.notify(f"Erro na inspeção: {exc}", severity="error")
            return

        self._set_busy(False, "Inspeção concluída.")
        for line in _format_inspection(result):
            log.write(line)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "inspect-run":
            self.run_worker(self._run())

    async def on_input_submitted(self, _event: Input.Submitted) -> None:
        await self._run()

    def action_inspect(self) -> None:
        self.run_worker(self._run())


# Formata o resultado da inspeção para o painel.
def _format_inspection(result: DetectionResult) -> list[str]:
    page = result.page
    lines = [
        f"URL: {page.url}",
        f"Título: {page.title or '(sem título)'}",
        f"Formulários: {page.form_count}",
        f"Campos: {len(result.fields)}",
    ]
    if page.iframe_urls:
        lines.append(f"Iframes: {len(page.iframe_urls)}")

    if result.warnings:
        lines.append("")
        lines.append("Avisos:")
        lines.extend(f"  - {warning}" for warning in result.warnings)

    if result.fields:
        lines.append("")
        lines.append("Campos detectados:")
        for field in result.fields:
            required = "sim" if field.required else "não"
            label = field.label or "(sem rótulo)"
            lines.append(
                f"  {field.field_id} | {label_for(FIELD_TYPE_LABELS, field.field_type)} | "
                f"obrigatório={required} | {label}"
            )
            if field.options:
                lines.append(f"      opções: {', '.join(field.options)}")

    return lines
