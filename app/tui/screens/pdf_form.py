# Tela de revisão e preenchimento de PDF em tempo real.

from __future__ import annotations

from contextlib import contextmanager
from functools import partial
from pathlib import Path
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
    Input,
    ProgressBar,
    RichLog,
    Select,
    Static,
    TextArea,
)

from app.schemas.pdf import (
    PdfFieldRecord,
    PdfFieldStatus,
    PdfFieldType,
    PdfFormSessionDetail,
    PdfSuggestionBatch,
)
from app.tui.labels import (
    PDF_FIELD_STATUS_LABELS,
    PDF_FIELD_TYPE_LABELS,
    PDF_SUGGESTION_SOURCE_LABELS,
    label_for,
)
from app.tui.services import TuiServices
from app.tui.widgets.modals import ConfirmModal, PdfOutputModal
from app.tui.workers import run_blocking


# Tela principal de revisão de um formulário PDF.
class PdfFormScreen(Screen):
    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "back", "Voltar"),
        ("s", "suggest", "Sugerir"),
        ("a", "approve_all", "Aprovar todos"),
        ("ctrl+r", "refresh_suggestions", "Regerar"),
    ]

    def __init__(
        self,
        services: TuiServices,
        source_id: int,
        session_id: int | None = None,
    ) -> None:
        super().__init__()
        self.services = services
        self.source_id = source_id
        self.session_id = session_id
        self.session: PdfFormSessionDetail | None = None
        self.fields: dict[str, PdfFieldRecord] = {}
        self.selected_field: str | None = None
        self._syncing = False
        self._busy = False
        self._cancel_requested = False
        self._suggestion_worker = None
        self._save_timer = None
        self._pending_field: str | None = None
        self._pending_value: str | None = None
        self._warnings: list[str] = []
        self._table_ready = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(classes="screen-body pdf-form-body"):
            yield Static("Preencher PDF", id="pdf-form-title", classes="title")
            yield Static("Carregando formulário...", id="pdf-form-status", classes="hint")
            yield ProgressBar(
                total=0,
                show_percentage=False,
                show_eta=False,
                id="pdf-form-progress",
            )
            with Horizontal(classes="pdf-main"):
                with Vertical(classes="pdf-fields-column"):
                    yield DataTable(id="pdf-fields-table", classes="table")
                with Vertical(id="pdf-editor", classes="pdf-editor"):
                    yield Static("", id="pdf-field-meta")
                    yield Static("", id="pdf-field-suggestion")
                    yield Input(
                        placeholder="Digite o valor do campo",
                        id="pdf-field-input",
                    )
                    yield TextArea(id="pdf-field-textarea")
                    yield Select(
                        [],
                        prompt="Selecione um valor",
                        allow_blank=True,
                        id="pdf-field-select",
                    )
                    with Horizontal(classes="actions"):
                        yield Button("Aplicar sugestão", id="pdf-apply")
                        yield Button("Aprovar", id="pdf-approve")
                        yield Button("Limpar", id="pdf-clear")
            with Horizontal(classes="actions"):
                yield Button("Sugerir", id="pdf-suggest", variant="primary")
                yield Button("Cancelar", id="pdf-cancel")
                yield Button("Aprovar todos", id="pdf-approve-all")
                yield Button("Preencher e salvar", id="pdf-fill")
                yield Button("Voltar", id="pdf-back")
            yield RichLog(id="pdf-warnings", markup=False, wrap=True, classes="pdf-warnings")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#pdf-fields-table", DataTable)
        table.cursor_type = "row"
        self._hide_editors()
        self._load_session()

    # Carrega ou cria a sessão persistida da fonte.
    def _load_session(self) -> None:
        try:
            if self.session_id is not None:
                session = self.services.pdf_forms.get_session(self.session_id)
            else:
                session = self.services.pdf_forms.open_session(self.source_id)
        except Exception as exc:  # noqa: BLE001
            self._status(f"Erro ao abrir formulário: {exc}", error=True)
            return

        self.session = session
        self.session_id = session.id
        self.fields = {field.field_name: field for field in session.fields}
        self._prepare_table()
        self._render_all()
        self._update_progress(session.generation_progress, session.generation_total)
        self._status(
            f"Sessão {session.id} — {session.source_title or 'PDF'} — "
            f"{len(self.fields)} campo(s)."
        )

        if self.fields:
            self.query_one("#pdf-fields-table", DataTable).move_cursor(row=0)
            first = next(iter(self.fields))
            self._select_field(first)

    # Prepara as colunas da tabela.
    def _prepare_table(self) -> None:
        table = self.query_one("#pdf-fields-table", DataTable)
        if not self._table_ready:
            table.add_columns(
                ("Campo", "name"),
                ("Tipo", "type"),
                ("Obrig.", "required"),
                ("Valor", "value"),
                ("Confiança", "confidence"),
                ("Situação", "status"),
            )
            self._table_ready = True
        table.clear(columns=False)

    # Renderiza todos os campos na tabela.
    def _render_all(self) -> None:
        table = self.query_one("#pdf-fields-table", DataTable)
        table.clear(columns=False)
        for field in self.fields.values():
            table.add_row(*self._row_values(field), key=field.field_name)

    # Atualiza uma linha específica.
    def _render_field(self, field: PdfFieldRecord) -> None:
        table = self.query_one("#pdf-fields-table", DataTable)
        values = self._row_values(field)
        table.update_cell(field.field_name, "type", values[1])
        table.update_cell(field.field_name, "required", values[2])
        table.update_cell(field.field_name, "value", values[3])
        table.update_cell(field.field_name, "confidence", values[4])
        table.update_cell(field.field_name, "status", values[5])

    # Monta os valores das colunas de um campo.
    def _row_values(self, field: PdfFieldRecord) -> tuple[str, ...]:
        value = field.final_value or field.suggested_value or field.current_value or "—"
        confidence = f"{field.confidence:.2f}" if field.confidence is not None else "—"
        return (
            field.field_name,
            label_for(PDF_FIELD_TYPE_LABELS, field.field_type),
            "Sim" if field.required else "Não",
            value,
            confidence,
            label_for(PDF_FIELD_STATUS_LABELS, field.status),
        )

    # Atualiza o progresso da geração.
    def _update_progress(self, completed: int, total: int) -> None:
        bar = self.query_one("#pdf-form-progress", ProgressBar)
        if total > 0:
            bar.update(total=total, progress=min(completed, total))
        else:
            bar.update(total=None, progress=0)

    # Mostra uma mensagem de status.
    def _status(self, message: str, *, error: bool = False) -> None:
        self.query_one("#pdf-form-status", Static).update(message)
        if error:
            self.notify(message, severity="error")

    # Escreve um aviso no painel inferior.
    def _warning(self, message: str) -> None:
        if not message or message in self._warnings:
            return
        self._warnings.append(message)
        self.query_one("#pdf-warnings", RichLog).write(f"Aviso: {message}")

    # Marca o formulário como ocupado.
    def _set_busy(self, busy: bool, message: str = "") -> None:
        self._busy = busy
        for button_id in (
            "#pdf-suggest",
            "#pdf-approve-all",
            "#pdf-fill",
            "#pdf-back",
        ):
            self.query_one(button_id, Button).disabled = busy
        self.query_one("#pdf-cancel", Button).disabled = not busy
        if message:
            self._status(message)

    # Suspende temporariamente o autosave durante atualizações programáticas.
    @contextmanager
    def _suspend_autosave(self):
        self._syncing = True
        try:
            yield
        finally:
            self.call_after_refresh(self._resume_autosave)

    # Reativa o autosave depois que os eventos pendentes forem processados.
    def _resume_autosave(self) -> None:
        self._syncing = False

    # Escolhe o campo selecionado e atualiza o editor.
    def _select_field(self, field_name: str) -> None:
        field = self.fields.get(field_name)
        if field is None:
            return
        self.selected_field = field_name
        with self._suspend_autosave():
            self._render_editor(field)

    # Preenche o painel de edição com o campo selecionado.
    def _render_editor(self, field: PdfFieldRecord) -> None:
        source = label_for(PDF_SUGGESTION_SOURCE_LABELS, field.suggestion_source or "")
        confidence = f"{field.confidence:.2f}" if field.confidence is not None else "—"
        self.query_one("#pdf-field-meta", Static).update(
            "\n".join(
                [
                    f"{field.label or field.field_name}",
                    f"Campo: {field.field_name}",
                    f"Tipo: {label_for(PDF_FIELD_TYPE_LABELS, field.field_type)}",
                    f"Obrigatório: {'sim' if field.required else 'não'}",
                    f"Somente leitura: {'sim' if field.readonly else 'não'}",
                    f"Página: {field.page_number or '—'}",
                ]
            )
        )
        suggestion = field.suggested_value or "(sem sugestão)"
        rationale = field.rationale or ""
        self.query_one("#pdf-field-suggestion", Static).update(
            f"Sugestão: {suggestion}\nOrigem: {source} | Confiança: {confidence}"
            + (f"\n{rationale}" if rationale else "")
        )

        editable = not field.readonly and field.field_type not in {
            PdfFieldType.SIGNATURE,
            PdfFieldType.UNKNOWN,
        }
        value = field.final_value
        if value is None:
            value = field.suggested_value
        if value is None:
            value = field.current_value
        value = value or ""

        input_widget = self.query_one("#pdf-field-input", Input)
        textarea = self.query_one("#pdf-field-textarea", TextArea)
        select = self.query_one("#pdf-field-select", Select)
        self._hide_editors()

        if field.field_type == PdfFieldType.TEXTAREA:
            textarea.display = True
            textarea.text = value
            textarea.disabled = not editable
        elif field.field_type in {
            PdfFieldType.CHOICE,
            PdfFieldType.RADIO,
            PdfFieldType.CHECKBOX,
        }:
            select.display = True
            options = [
                (option.label or option.value, option.value)
                for option in field.options
            ]
            if field.field_type == PdfFieldType.CHECKBOX and not any(
                option.value == "Off" for option in field.options
            ):
                options.append(("Desmarcado", "Off"))
            select.set_options(options)
            select.disabled = not editable
            select.value = value if value else Select.BLANK
        else:
            input_widget.display = True
            input_widget.value = value
            input_widget.disabled = not editable

        for button_id in ("#pdf-apply", "#pdf-approve", "#pdf-clear"):
            self.query_one(button_id, Button).disabled = not editable

    # Esconde todos os editores possíveis.
    def _hide_editors(self) -> None:
        for widget_id in ("#pdf-field-input", "#pdf-field-textarea", "#pdf-field-select"):
            self.query_one(widget_id).display = False

    # Lê o valor atual do editor exibido.
    def _editor_value(self) -> str:
        select = self.query_one("#pdf-field-select", Select)
        if select.display:
            return "" if select.value in (Select.BLANK, None) else str(select.value)
        textarea = self.query_one("#pdf-field-textarea", TextArea)
        if textarea.display:
            return textarea.text
        return self.query_one("#pdf-field-input", Input).value

    # Agenda a persistência do valor editado.
    def _queue_save(self, value: str, *, force: bool = False) -> None:
        field_name = self.selected_field
        if field_name is None or (self._syncing and not force):
            return
        field = self.fields.get(field_name)
        if field is None or field.readonly:
            return

        self._pending_field = field_name
        self._pending_value = value
        updated = field.model_copy(
            update={
                "final_value": value or None,
                "status": PdfFieldStatus.EDITED,
            }
        )
        self.fields[field_name] = updated
        self._render_field(updated)
        self._status("Salvando alteração...")

        if self._save_timer is not None:
            self._save_timer.stop()
        self._save_timer = self.set_timer(0.35, self._start_pending_save)

    # Dispara o worker de autosave.
    def _start_pending_save(self) -> None:
        if self._pending_field is not None:
            self.run_worker(self._persist_pending(), group="pdf-save")

    # Persiste o valor pendente de forma assíncrona.
    async def _persist_pending(self) -> None:
        field_name = self._pending_field
        value = self._pending_value
        self._save_timer = None
        self._pending_field = None
        self._pending_value = None
        if field_name is None or self.session is None:
            return

        try:
            field = await run_blocking(
                self,
                self.services.pdf_forms.update_field_live,
                self.session.id,
                field_name,
                value,
            )
        except Exception as exc:  # noqa: BLE001
            self._status(f"Erro ao salvar '{field_name}': {exc}", error=True)
            return

        if self._pending_field == field_name:
            return
        self.fields[field_name] = field
        self._render_field(field)
        if self.selected_field == field_name:
            with self._suspend_autosave():
                self._render_editor(field)
        self._status("Alteração salva.")

    # Confere se o valor já corresponde ao estado atual do campo.
    def _matches_editor_value(self, value: str) -> bool:
        if self.selected_field is None:
            return False
        field = self.fields.get(self.selected_field)
        if field is None:
            return False
        return value in {
            field.final_value,
            field.suggested_value,
            field.current_value,
        }

    # Trata mudanças de texto em campos simples.
    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "pdf-field-input" or self._syncing:
            return
        if self._matches_editor_value(event.value):
            return
        self._queue_save(event.value)

    # Trata mudanças em campos de texto longo.
    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id != "pdf-field-textarea" or self._syncing:
            return
        if self._matches_editor_value(event.text_area.text):
            return
        self._queue_save(event.text_area.text)

    # Trata mudanças de seleção.
    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "pdf-field-select" or self._syncing:
            return
        value = "" if event.value in (Select.BLANK, None) else str(event.value)
        if self._matches_editor_value(value):
            return
        self._queue_save(value)

    # Atualiza o editor ao trocar a linha selecionada.
    def on_data_table_row_highlighted(
        self,
        event: DataTable.RowHighlighted,
    ) -> None:
        key = event.row_key.value if hasattr(event.row_key, "value") else str(event.row_key)
        self._select_field(str(key))

    # Inicia ou reinicia a geração de sugestões.
    def action_suggest(self) -> None:
        self._start_suggestions(refresh=True)

    # Força a regeneração das sugestões.
    def action_refresh_suggestions(self) -> None:
        self._start_suggestions(refresh=True)

    # Inicia o worker de sugestões progressivas.
    def _start_suggestions(self, *, refresh: bool) -> None:
        if self._busy or self.session is None:
            return
        self._cancel_requested = False
        self._set_busy(True, "Gerando sugestões em tempo real...")
        session_id = self.session.id

        def worker() -> None:
            try:
                for batch in self.services.pdf_forms.suggest_live(
                    session_id,
                    refresh=refresh,
                ):
                    if self._cancel_requested:
                        break
                    self.app.call_from_thread(self._apply_batch, batch)
            except Exception as exc:  # noqa: BLE001
                self.app.call_from_thread(
                    self._suggestion_failed,
                    str(exc),
                )
                return
            self.app.call_from_thread(self._suggestion_finished)

        self._suggestion_worker = self.run_worker(
            worker,
            thread=True,
            group="pdf-suggest",
            exclusive=True,
        )

    # Aplica um lote de sugestões recebido do worker.
    def _apply_batch(self, batch: PdfSuggestionBatch) -> None:
        for field in batch.fields:
            self.fields[field.field_name] = field
            self._render_field(field)
        for warning in batch.warnings:
            self._warning(warning)
        self._update_progress(batch.completed, batch.total)
        if batch.done:
            self._status(
                f"Sugestões concluídas: {batch.completed}/{batch.total}."
            )

        if self.selected_field and self.selected_field not in {
            self._pending_field,
        }:
            selected = self.fields.get(self.selected_field)
            if selected is not None:
                with self._suspend_autosave():
                    self._render_editor(selected)

    # Finaliza o estado visual da geração.
    def _suggestion_finished(self) -> None:
        self._set_busy(False)
        if self._cancel_requested:
            self._status("Geração de sugestões cancelada.")
        elif self.session_id is not None:
            try:
                session = self.services.pdf_forms.get_session(self.session_id)
            except Exception:  # noqa: BLE001
                return
            self.session = session
            self.fields = {field.field_name: field for field in session.fields}
            self._update_progress(
                session.generation_progress,
                session.generation_total,
            )
            self._status(
                f"Revisão pronta: {len(self.fields)} campo(s). "
                "Edite os valores e aprove antes de salvar."
            )

    # Exibe erro da geração.
    def _suggestion_failed(self, message: str) -> None:
        self._set_busy(False)
        self._status(f"Erro ao gerar sugestões: {message}", error=True)

    # Cancela a geração atual.
    def action_cancel(self) -> None:
        if not self._busy:
            return
        self._cancel_requested = True
        if self._suggestion_worker is not None:
            self._suggestion_worker.cancel()
        self._status("Cancelando geração...")

    # Aprova o campo selecionado.
    def action_approve(self) -> None:
        if self.selected_field is None or self.session is None:
            return
        self.run_worker(self._approve_selected(), group="pdf-approve")

    # Executa a aprovação do campo selecionado.
    async def _approve_selected(self) -> None:
        field_name = self.selected_field
        if field_name is None or self.session is None:
            return
        try:
            field = await run_blocking(
                self,
                self.services.pdf_forms.approve_field,
                self.session.id,
                field_name,
            )
        except Exception as exc:  # noqa: BLE001
            self._status(f"Erro ao aprovar: {exc}", error=True)
            return
        self.fields[field_name] = field
        self._render_field(field)
        self._select_field(field_name)
        self._status(f"Campo '{field.label or field_name}' aprovado.")

    # Aprova todos os campos com valor.
    def action_approve_all(self) -> None:
        if self.session is None or self._busy:
            return
        self.run_worker(self._approve_all(), group="pdf-approve")

    # Executa a aprovação em massa.
    async def _approve_all(self) -> None:
        if self.session is None:
            return
        self._set_busy(True, "Aprovando campos...")
        try:
            session = await run_blocking(
                self,
                self.services.pdf_forms.approve_all,
                self.session.id,
            )
        except Exception as exc:  # noqa: BLE001
            self._set_busy(False)
            self._status(f"Erro ao aprovar campos: {exc}", error=True)
            return
        self._set_busy(False)
        self.session = session
        self.fields = {field.field_name: field for field in session.fields}
        self._render_all()
        if self.selected_field:
            self._select_field(self.selected_field)
        self._status("Campos com valor foram aprovados.")

    # Aplica a sugestão ao editor.
    def action_apply_suggestion(self) -> None:
        if self.selected_field is None:
            return
        field = self.fields.get(self.selected_field)
        if field is None or field.suggested_value is None:
            self.notify("Este campo não possui sugestão.", severity="warning")
            return
        with self._suspend_autosave():
            if field.field_type in {
                PdfFieldType.CHOICE,
                PdfFieldType.RADIO,
                PdfFieldType.CHECKBOX,
            }:
                select = self.query_one("#pdf-field-select", Select)
                select.value = field.suggested_value
            elif field.field_type == PdfFieldType.TEXTAREA:
                self.query_one("#pdf-field-textarea", TextArea).text = (
                    field.suggested_value
                )
            else:
                self.query_one("#pdf-field-input", Input).value = field.suggested_value
        self._queue_save(field.suggested_value, force=True)

    # Limpa o valor do campo selecionado.
    def action_clear_field(self) -> None:
        if self.selected_field is None:
            return
        with self._suspend_autosave():
            self.query_one("#pdf-field-input", Input).value = ""
            self.query_one("#pdf-field-textarea", TextArea).text = ""
            self.query_one("#pdf-field-select", Select).value = Select.BLANK
        self._queue_save("", force=True)

    # Abre o modal para escolher o arquivo de saída.
    def action_fill(self) -> None:
        if self.session is None or self._busy:
            return
        self.app.push_screen(
            PdfOutputModal(self._default_output_path()),
            self._after_output_path,
        )

    # Recebe o caminho e confirma sobrescrita quando necessário.
    async def _after_output_path(self, result: object) -> None:
        if not isinstance(result, str) or not result.strip():
            return
        path = Path(result).expanduser()
        if path.exists():
            self.app.push_screen(
                ConfirmModal(
                    f"O arquivo '{path}' já existe. Deseja substituí-lo?",
                    title="Substituir arquivo",
                ),
                partial(self._after_overwrite, path),
            )
            return
        await self._start_fill(path)

    # Confirma a substituição e inicia o preenchimento.
    async def _after_overwrite(self, path: Path, confirmed: bool) -> None:
        if confirmed:
            await self._start_fill(path)

    # Executa o preenchimento em thread.
    async def _start_fill(self, path: Path) -> None:
        if self.session is None:
            return
        if self._pending_field is not None:
            try:
                self.services.pdf_forms.update_field_live(
                    self.session.id,
                    self._pending_field,
                    self._pending_value,
                )
            except Exception as exc:  # noqa: BLE001
                self._status(f"Erro ao salvar edição pendente: {exc}", error=True)
                return
            self._pending_field = None
            self._pending_value = None
            if self._save_timer is not None:
                self._save_timer.stop()
                self._save_timer = None

        self._set_busy(True, "Preenchendo e salvando o PDF...")
        try:
            result = await run_blocking(
                self,
                self.services.pdf_forms.fill,
                self.session.id,
                str(path),
            )
        except Exception as exc:  # noqa: BLE001
            self._set_busy(False)
            self._status(f"Erro ao preencher PDF: {exc}", error=True)
            return

        self._set_busy(False)
        for warning in result.warnings:
            self._warning(warning)
        self._status(f"PDF preenchido salvo em {result.output_path}")
        self.notify(f"PDF preenchido: {result.output_path}", severity="information")

    # Devolve um caminho de saída padrão ao lado do original.
    def _default_output_path(self) -> str:
        session_id = self.session_id or 0
        try:
            detail = self.services.sources.get_source(self.source_id)
            if detail.snapshot and detail.snapshot.raw_path:
                return str(
                    Path(detail.snapshot.raw_path).expanduser().parent
                    / f"preenchido-{session_id}.pdf"
                )
        except Exception:  # noqa: BLE001
            return str(Path.cwd() / f"preenchido-{session_id}.pdf")
        return str(Path.cwd() / f"preenchido-{session_id}.pdf")

    # Persiste edição pendente e volta.
    def action_back(self) -> None:
        if self._pending_field is not None and self.session is not None:
            try:
                self.services.pdf_forms.update_field_live(
                    self.session.id,
                    self._pending_field,
                    self._pending_value,
                )
            except Exception as exc:  # noqa: BLE001
                self._status(f"Erro ao salvar edição: {exc}", error=True)
                return
            self._pending_field = None
            self._pending_value = None
        if self._suggestion_worker is not None:
            self._suggestion_worker.cancel()
        self.app.pop_screen()

    # Liga botões aos atalhos correspondentes.
    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "pdf-suggest":
                self.action_suggest()
            case "pdf-cancel":
                self.action_cancel()
            case "pdf-approve-all":
                self.action_approve_all()
            case "pdf-approve":
                self.action_approve()
            case "pdf-apply":
                self.action_apply_suggestion()
            case "pdf-clear":
                self.action_clear_field()
            case "pdf-fill":
                self.action_fill()
            case "pdf-back":
                self.action_back()
