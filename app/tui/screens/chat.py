# Painel de conversa com o agente dentro de uma área de trabalho.

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Button, Input, RichLog, Static, TabbedContent

from app.schemas.rag import (
    ChatAnswer,
    ChatMessage,
    ChatStatus,
    answer_from_record,
)
from app.tui.labels import RETRIEVAL_MODE_LABELS, label_for
from app.tui.services import TuiServices
from app.tui.widgets.modals import ConfirmModal
from app.tui.workers import run_blocking


# Painel de chat contextualizado no workspace selecionado.
class ChatPane(Widget):
    BINDINGS: ClassVar[list[BindingType]] = [
        ("ctrl+l", "clear", "Limpar conversa"),
    ]

    def __init__(
        self,
        services: TuiServices,
        workspace_id: int,
        workspace_name: str,
    ) -> None:
        super().__init__()
        self.services = services
        self.workspace_id = workspace_id
        self.workspace_name = workspace_name
        self.history: list[ChatMessage] = []
        self._busy = False

    def compose(self) -> ComposeResult:
        with Vertical(classes="pane-body"):
            yield Static(
                f"Conversa — {self.workspace_name}",
                classes="section-title",
            )
            yield Static("Carregando situação do índice...", id="chat-status", classes="hint")
            yield RichLog(id="chat-log", markup=False, wrap=True, classes="chat-log")
            with Horizontal(classes="chat-controls"):
                yield Input(
                    placeholder="Digite sua pergunta...",
                    id="chat-input",
                )
                yield Input(
                    placeholder="top-k",
                    id="chat-top-k",
                    classes="small-input",
                )
                yield Button("Enviar", id="chat-send", variant="primary")
                yield Button("Fontes", id="chat-sources")
                yield Button("Limpar", id="chat-clear")

    def on_mount(self) -> None:
        self._refresh_status()
        self._write(
            "Agente de Editais",
            "Pergunte sobre o edital ou peça sugestões. As fontes indexadas "
            "serão usadas quando estiverem disponíveis.",
        )
        self._restore_conversation()

    # Recupera e exibe a conversa salva da área de trabalho.
    def _restore_conversation(self) -> None:
        try:
            records = self.services.chat.conversation(self.workspace_id)
        except Exception as exc:  # noqa: BLE001
            self._write("Erro", f"Não foi possível carregar a conversa salva: {exc}")
            return

        if not records:
            return

        for record in records:
            if record.role == "user":
                self._write("Você", record.content)
                continue

            answer = answer_from_record(record)
            self._write(
                "Agente",
                _format_answer(answer) if answer is not None else record.content,
            )

        self.history = [
            ChatMessage(role=record.role, content=record.content)
            for record in records
        ]
        self._write(
            "Agente de Editais",
            f"Conversa anterior restaurada ({len(records)} mensagens).",
        )

    # Atualiza o cabeçalho com a situação do índice.
    def _refresh_status(self) -> None:
        try:
            status = self.services.chat.status(self.workspace_id)
        except Exception as exc:  # noqa: BLE001
            self.query_one("#chat-status", Static).update(
                f"Erro ao consultar o índice: {exc}"
            )
            return

        self.query_one("#chat-status", Static).update(_format_status(status))

    # Escreve uma mensagem formatada no histórico visual.
    def _write(self, author: str, message: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.write(f"[{author}]")
        log.write(message)
        log.write("")

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self._busy = busy
        for widget_id in ("#chat-send", "#chat-clear", "#chat-sources"):
            self.query_one(widget_id, Button).disabled = busy
        if message:
            self.query_one("#chat-status", Static).update(message)

    # Lê o top-k informado, usando o padrão quando estiver vazio.
    def _top_k(self) -> int | None:
        raw = self.query_one("#chat-top-k", Input).value.strip()
        if not raw:
            return None
        try:
            value = int(raw)
        except ValueError as exc:
            raise ValueError("O top-k deve ser um número inteiro.") from exc
        if value < 1:
            raise ValueError("O top-k deve ser pelo menos 1.")
        return value

    async def _send(self) -> None:
        if self._busy:
            return

        question = self.query_one("#chat-input", Input).value.strip()
        if not question:
            self.notify("Digite uma pergunta.", severity="warning")
            return

        try:
            top_k = self._top_k()
        except ValueError as exc:
            self.notify(str(exc), severity="error")
            return

        self._write("Você", question)
        self.query_one("#chat-input", Input).value = ""
        self._set_busy(True, "Consultando o agente...")

        try:
            answer = await run_blocking(
                self,
                self.services.chat.ask,
                self.workspace_id,
                question,
                top_k=top_k,
                history=self.history,
            )
        except Exception as exc:  # noqa: BLE001
            self._set_busy(False)
            self._refresh_status()
            self._write("Erro", str(exc))
            self.notify(f"Erro ao consultar o agente: {exc}", severity="error")
            self.query_one("#chat-input", Input).focus()
            return

        self._set_busy(False)
        self._refresh_status()
        self._write("Agente", _format_answer(answer))
        self.history.append(ChatMessage(role="user", content=question))
        self.history.append(ChatMessage(role="assistant", content=answer.answer))
        self.query_one("#chat-input", Input).focus()

    def _clear(self) -> None:
        self.app.push_screen(
            ConfirmModal(
                (
                    "Limpar toda a conversa salva desta área de trabalho? "
                    "As perguntas e respostas antigas serão removidas. "
                    "Esta ação não pode ser desfeita."
                ),
                title="Limpar conversa",
            ),
            self._after_clear,
        )

    async def _after_clear(self, confirmed: object) -> None:
        if confirmed is not True:
            return

        try:
            self.services.chat.clear_conversation(self.workspace_id)
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Erro ao limpar conversa: {exc}", severity="error")
            return

        self.query_one("#chat-log", RichLog).clear()
        self.history.clear()
        self._write(
            "Agente de Editais",
            "Histórico limpo. Envie uma nova pergunta quando quiser.",
        )
        self.notify("Conversa limpa.", severity="information")

    def _show_sources(self) -> None:
        tabs = self.screen.query_one("#workspace-tabs", TabbedContent)
        tabs.active = "tab-sources"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "chat-send":
                self.run_worker(self._send())
            case "chat-clear":
                self._clear()
            case "chat-sources":
                self._show_sources()

    async def on_input_submitted(self, _event: Input.Submitted) -> None:
        await self._send()

    def action_clear(self) -> None:
        self._clear()


# Formata a situação do índice para o cabeçalho.
def _format_status(status: ChatStatus) -> str:
    model = status.embedding_model or "não configurado"
    return (
        f"Fontes: {status.sources_total} (prontas: {status.sources_ready}) — "
        f"Trechos: {status.chunks_total} "
        f"(com embeddings: {status.chunks_embedded}) — "
        f"Modelo de embedding: {model}"
    )


# Formata uma resposta com citações e avisos.
def _format_answer(answer: ChatAnswer) -> str:
    lines = [answer.answer]
    if answer.mode is not None:
        lines.append(
            f"\nModo de busca: {label_for(RETRIEVAL_MODE_LABELS, answer.mode)}"
        )

    if answer.citations:
        lines.append("\nFontes citadas:")
        for citation in answer.citations:
            location: list[str] = []
            if citation.page_number is not None:
                location.append(f"página {citation.page_number}")
            if citation.section_title:
                location.append(citation.section_title)
            if citation.source_url:
                location.append(citation.source_url)
            suffix = " | " + " | ".join(location) if location else ""
            lines.append(
                f"  [{citation.marker}] {citation.source_title or 'Fonte'}{suffix}"
            )

    if answer.warnings:
        lines.append("\nAvisos:")
        lines.extend(f"  - {warning}" for warning in answer.warnings)
    return "\n".join(lines)
