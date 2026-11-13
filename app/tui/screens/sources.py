# Telas de fontes: listagem, ingestão, indexação e leitura.

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Button, DataTable, Footer, Header, Static

from app.schemas.source import Source, SourceDetail
from app.tui.labels import (
    SOURCE_KIND_LABELS,
    SOURCE_STATUS_LABELS,
    label_for,
)
from app.tui.services import TuiServices
from app.tui.widgets.modals import SourceFileModal, SourceUrlModal
from app.tui.workers import run_blocking


# Formata a origem da fonte para exibição.
def _source_origin(source: Source) -> str:
    return source.url or source.final_url or "Arquivo local"


# Painel de fontes exibido dentro de uma área de trabalho.
class SourcesPane(Widget):
    BINDINGS: ClassVar[list[BindingType]] = [
        ("a", "new_url", "Adicionar URL"),
        ("f", "new_file", "Adicionar arquivo"),
        ("i", "index", "Indexar"),
        ("r", "refresh", "Atualizar"),
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
        self._table_ready = False
        self._busy = False

    def compose(self) -> ComposeResult:
        with Vertical(classes="pane-body"):
            yield Static("Fontes", classes="section-title")
            yield DataTable(id="sources-table", classes="table")
            yield Static(
                "Selecione uma fonte para ver os detalhes.",
                id="sources-status",
                classes="hint",
            )
            with Horizontal(classes="actions"):
                yield Button("Adicionar URL", id="add-url", variant="primary")
                yield Button("Adicionar arquivo", id="add-file")
                yield Button("Indexar selecionada", id="index-one")
                yield Button("Indexar todas", id="index-all")
                yield Button("Atualizar", id="refresh")

    def on_mount(self) -> None:
        self._load()

    # Carrega as fontes da área de trabalho.
    def _load(self) -> None:
        table = self.query_one("#sources-table", DataTable)
        table.cursor_type = "row"
        if not self._table_ready:
            table.add_columns("ID", "Título", "Tipo", "Situação", "Origem")
            self._table_ready = True
        table.clear(columns=False)

        try:
            sources = self.services.sources.list_sources(self.workspace_id)
        except Exception as exc:  # noqa: BLE001
            self._status(f"Erro ao carregar fontes: {exc}", error=True)
            return

        for source in sources:
            table.add_row(
                str(source.id),
                source.title or "(sem título)",
                label_for(SOURCE_KIND_LABELS, source.source_kind),
                label_for(SOURCE_STATUS_LABELS, source.status),
                _source_origin(source),
                key=str(source.id),
            )

        if not sources:
            self._status("Nenhuma fonte cadastrada nesta área de trabalho.")
        else:
            self._status(f"{len(sources)} fonte(s) cadastrada(s).")

    # Atualiza a linha de status do painel.
    def _status(self, message: str, *, error: bool = False) -> None:
        status = self.query_one("#sources-status", Static)
        status.update(message)
        if error:
            self.notify(message, severity="error")

    # Marca o painel como ocupado e atualiza o status.
    def _set_busy(self, busy: bool, message: str = "") -> None:
        self._busy = busy
        for button_id in (
            "#add-url",
            "#add-file",
            "#index-one",
            "#index-all",
            "#refresh",
        ):
            self.query_one(button_id, Button).disabled = busy
        if message:
            self.query_one("#sources-status", Static).update(message)

    # Devolve a fonte selecionada, se houver.
    def _selected_source_id(self) -> int | None:
        table = self.query_one("#sources-table", DataTable)
        if table.row_count == 0:
            return None
        row = table.get_row_at(table.cursor_coordinate.row)
        return int(row[0])

    def _open_selected(self) -> None:
        source_id = self._selected_source_id()
        if source_id is None:
            self.notify("Selecione uma fonte.", severity="warning")
            return
        self.app.push_screen(SourceDetailScreen(self.services, source_id))

    def action_new_url(self) -> None:
        if self._busy:
            return
        self.app.push_screen(
            SourceUrlModal(self.workspace_name),
            self._after_add_url,
        )

    def action_new_file(self) -> None:
        if self._busy:
            return
        self.app.push_screen(
            SourceFileModal(self.workspace_name),
            self._after_add_file,
        )

    async def _after_add_url(self, result: object) -> None:
        if not isinstance(result, tuple) or len(result) != 4:
            return
        url, use_browser, follow_pdfs, max_links = result
        self._set_busy(True, "Ingerindo URL...")
        try:
            ingestion = await run_blocking(
                self,
                self.services.sources.add_url,
                self.workspace_id,
                str(url),
                use_browser=bool(use_browser),
                follow_pdfs=bool(follow_pdfs),
                max_links=max_links,
            )
        except Exception as exc:  # noqa: BLE001
            self._set_busy(False)
            self._status(f"Erro ao ingerir URL: {exc}", error=True)
            return

        self._set_busy(False)
        self._load()
        if ingestion.duplicate:
            message = (
                f"A fonte já estava cadastrada (id={ingestion.source.id})."
            )
        else:
            message = f"Fonte ingerida com situação {label_for(SOURCE_STATUS_LABELS, ingestion.source.status)}."
        if ingestion.children:
            message += f" {len(ingestion.children)} PDF(s) vinculado(s) ingerido(s)."
        if ingestion.warnings:
            message += f" {len(ingestion.warnings)} aviso(s)."
        self._status(message)
        self.notify(message, severity="information")

    async def _after_add_file(self, result: object) -> None:
        if not isinstance(result, str):
            return
        self._set_busy(True, "Ingerindo arquivo...")
        try:
            ingestion = await run_blocking(
                self,
                self.services.sources.add_file,
                self.workspace_id,
                result,
            )
        except Exception as exc:  # noqa: BLE001
            self._set_busy(False)
            self._status(f"Erro ao ingerir arquivo: {exc}", error=True)
            return

        self._set_busy(False)
        self._load()
        if ingestion.duplicate:
            message = f"A fonte já estava cadastrada (id={ingestion.source.id})."
        else:
            message = f"Fonte ingerida com situação {label_for(SOURCE_STATUS_LABELS, ingestion.source.status)}."
        self._status(message)
        self.notify(message, severity="information")

    async def _index(self, source_id: int | None) -> None:
        if self._busy:
            return
        self._set_busy(True, "Indexando fontes...")
        try:
            result = await run_blocking(
                self,
                self.services.indexing.index_workspace,
                self.workspace_id,
                source_id=source_id,
            )
        except Exception as exc:  # noqa: BLE001
            self._set_busy(False)
            self._status(f"Erro ao indexar: {exc}", error=True)
            return

        self._set_busy(False)
        message = (
            f"Indexação concluída: {result.sources_indexed} fonte(s), "
            f"{result.chunks_created} trecho(s), "
            f"{result.embeddings_created} embedding(s)."
        )
        if result.sources_skipped:
            message += f" {result.sources_skipped} fonte(s) ignorada(s)."
        if result.warnings:
            message += f" {len(result.warnings)} aviso(s)."
        self._status(message)
        self.notify(message, severity="information")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "add-url":
                self.action_new_url()
            case "add-file":
                self.action_new_file()
            case "index-one":
                source_id = self._selected_source_id()
                if source_id is None:
                    self.notify("Selecione uma fonte para indexar.", severity="warning")
                else:
                    self.run_worker(self._index(source_id))
            case "index-all":
                self.run_worker(self._index(None))
            case "refresh":
                self._load()

    def on_data_table_row_selected(
        self,
        _event: DataTable.RowSelected,
    ) -> None:
        self._open_selected()

    def action_index(self) -> None:
        source_id = self._selected_source_id()
        self.run_worker(self._index(source_id))

    def action_refresh(self) -> None:
        self._load()


# Tela de leitura do conteúdo extraído de uma fonte.
class SourceDetailScreen(Screen):
    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "back", "Voltar"),
        ("r", "reload", "Atualizar"),
    ]

    def __init__(self, services: TuiServices, source_id: int) -> None:
        super().__init__()
        self.services = services
        self.source_id = source_id

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(classes="screen-body"):
            yield Static("", id="source-title", classes="title")
            with VerticalScroll(id="source-content", classes="detail-box"):
                yield Static("", id="source-meta")
                yield Static("", id="source-warnings")
                yield Static("", id="source-preview")
            with Horizontal(classes="actions"):
                yield Button("Voltar", id="back")
                yield Button("Atualizar", id="refresh")
        yield Footer()

    def on_mount(self) -> None:
        self._load()

    def _load(self) -> None:
        try:
            detail = self.services.sources.get_source(self.source_id)
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Erro ao carregar fonte: {exc}", severity="error")
            return

        self.query_one("#source-title", Static).update(
            detail.title or f"Fonte {detail.id}"
        )
        self.query_one("#source-meta", Static).update(_format_source_meta(detail))
        warnings = "\n".join(f"- {warning}" for warning in _source_warnings(detail))
        self.query_one("#source-warnings", Static).update(
            f"Avisos:\n{warnings}" if warnings else ""
        )
        snapshot = detail.snapshot
        preview = snapshot.content_text[:5000] if snapshot else ""
        self.query_one("#source-preview", Static).update(
            f"Prévia do conteúdo:\n\n{preview or '(sem texto extraído)'}"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.action_back()
        elif event.button.id == "refresh":
            self._load()

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_reload(self) -> None:
        self._load()


# Monta os metadados exibidos no detalhe da fonte.
def _format_source_meta(detail: SourceDetail) -> str:
    lines = [
        f"ID: {detail.id}",
        f"Área de trabalho: {detail.workspace_id}",
        f"Tipo: {label_for(SOURCE_KIND_LABELS, detail.source_kind)}",
        f"Situação: {label_for(SOURCE_STATUS_LABELS, detail.status)}",
        f"Título: {detail.title or '(sem título)'}",
        f"URL: {detail.url or '(arquivo local)'}",
        f"URL final: {detail.final_url or '(não informada)'}",
        f"Tipo de conteúdo: {detail.content_type or '(não informado)'}",
        f"SHA-256: {detail.sha256 or '(não informado)'}",
    ]
    if detail.error:
        lines.append(f"Erro: {detail.error}")

    snapshot = detail.snapshot
    if snapshot is not None:
        lines.extend(
            [
                f"Páginas: {snapshot.page_count}",
                f"Segmentos: {len(snapshot.segments)}",
                f"Caracteres: {len(snapshot.content_text)}",
                f"Arquivo original: {snapshot.raw_path}",
            ]
        )
    else:
        lines.append("Instantâneo: não disponível.")
    return "\n".join(lines)


# Devolve avisos da fonte e do snapshot.
def _source_warnings(detail: SourceDetail) -> list[str]:
    if detail.snapshot is None:
        return []
    return list(detail.snapshot.warnings)
