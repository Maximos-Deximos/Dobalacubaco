# Casos de uso de ingestão de editais web e arquivos locais.

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.config import Settings, get_settings
from app.ingestion.fetcher import (
    BrowserSourceFetcher,
    HttpSourceFetcher,
    detect_content_type,
    ensure_supported_content_type,
    is_pdf_resource,
)
from app.ingestion.html_extractor import HtmlExtractionError, HtmlExtractor
from app.ingestion.models import ExtractedDocument, FetchedResource
from app.ingestion.pdf_extractor import PdfExtractionError, PdfExtractor
from app.ingestion.storage import SourceStorage, StorageError
from app.memory.source_repository import SourceRepository
from app.memory.workspace_repository import WorkspaceRepository
from app.schemas.source import Source, SourceKind, SourceStatus


# Erro lançado quando a ingestão não pode ser concluída.
class SourceIngestionError(RuntimeError):
    pass


# Resultado de uma ingestão, incluindo documentos vinculados.
@dataclass(slots=True)
class IngestionResult:
    source: Source
    children: list[Source] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duplicate: bool = False


# Orquestra download, extração e persistência de fontes.
class SourceIngestionService:
    def __init__(
        self,
        settings: Settings | None = None,
        workspace_repository: WorkspaceRepository | None = None,
        source_repository: SourceRepository | None = None,
        storage: SourceStorage | None = None,
        http_fetcher: HttpSourceFetcher | None = None,
        browser_fetcher: BrowserSourceFetcher | None = None,
        html_extractor: HtmlExtractor | None = None,
        pdf_extractor: PdfExtractor | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.workspace_repository = workspace_repository or WorkspaceRepository(
            self.settings.database_url
        )
        self.source_repository = source_repository or SourceRepository(
            self.settings.database_url
        )
        self.storage = storage or SourceStorage(self.settings)
        self.http_fetcher = http_fetcher or HttpSourceFetcher(self.settings)
        self.browser_fetcher = browser_fetcher or BrowserSourceFetcher(self.settings)
        self.html_extractor = html_extractor or HtmlExtractor()
        self.pdf_extractor = pdf_extractor or PdfExtractor()

    # Baixa e ingere uma URL pública.
    def add_url(
        self,
        workspace_id: int,
        url: str,
        *,
        use_browser: bool = False,
        follow_pdfs: bool = False,
        max_links: int | None = None,
        parent_source_id: int | None = None,
    ) -> IngestionResult:
        self.workspace_repository.get(workspace_id)

        if use_browser:
            resource = asyncio.run(self.browser_fetcher.fetch(url))
        else:
            resource = self.http_fetcher.fetch(url)

        return self._ingest_resource(
            workspace_id=workspace_id,
            resource=resource,
            url=url,
            parent_source_id=parent_source_id,
            follow_pdfs=follow_pdfs,
            max_links=max_links,
        )

    # Ingere um arquivo HTML ou PDF já presente no disco.
    def add_file(self, workspace_id: int, path: str | Path) -> IngestionResult:
        self.workspace_repository.get(workspace_id)
        file_path = Path(path).expanduser()

        if not file_path.is_file():
            raise SourceIngestionError(f"Arquivo não encontrado: {file_path}")

        try:
            content = file_path.read_bytes()
        except OSError as exc:
            raise SourceIngestionError(
                f"Falha ao ler o arquivo '{file_path}': {exc}"
            ) from exc

        content_type = _content_type_for_file(file_path, content)
        resource = FetchedResource(
            content=content,
            content_type=content_type,
            final_url="",
            status_code=200,
            headers={},
        )

        return self._ingest_resource(
            workspace_id=workspace_id,
            resource=resource,
            url=None,
            parent_source_id=None,
            follow_pdfs=False,
            max_links=None,
            title_hint=file_path.stem,
        )

    # Lista as fontes de um workspace.
    def list_sources(self, workspace_id: int) -> list[Source]:
        self.workspace_repository.get(workspace_id)
        return self.source_repository.list_by_workspace(workspace_id)

    # Busca uma fonte com o snapshot extraído.
    def get_source(self, source_id: int):
        return self.source_repository.get_detail(source_id)

    # Exclui uma fonte, seus PDFs vinculados, índice e arquivos locais.
    def delete_source(self, source_id: int) -> Source:
        tree = self.source_repository.list_tree(source_id)
        deleted = self.source_repository.delete(source_id)

        # Remove os arquivos de cada fonte da árvore já apagada do banco.
        for source in tree:
            self.storage.delete_source(source.workspace_id, source.id)

        return deleted

    # Executa a extração e persistência de um recurso já baixado.
    def _ingest_resource(
        self,
        *,
        workspace_id: int,
        resource: FetchedResource,
        url: str | None,
        parent_source_id: int | None,
        follow_pdfs: bool,
        max_links: int | None,
        title_hint: str = "",
    ) -> IngestionResult:
        content_type = detect_content_type(resource.content, resource.content_type)
        ensure_supported_content_type(content_type)
        source_kind = (
            SourceKind.WEB_PDF
            if is_pdf_resource(resource.content, content_type) and url
            else SourceKind.UPLOADED_PDF
            if is_pdf_resource(resource.content, content_type)
            else SourceKind.WEB_PAGE
            if url
            else SourceKind.UPLOADED_HTML
        )

        sha256 = hashlib.sha256(resource.content).hexdigest()
        existing = self.source_repository.find_by_hash(workspace_id, sha256)
        if existing is not None:
            return IngestionResult(source=existing, duplicate=True)

        source = self.source_repository.create(
            workspace_id=workspace_id,
            source_kind=source_kind,
            url=url,
            parent_source_id=parent_source_id,
            title=title_hint,
            final_url=resource.final_url or None,
            content_type=content_type,
            sha256=sha256,
            status=SourceStatus.EXTRACTING,
        )

        try:
            document, extension = self._extract_document(
                resource=resource,
                content_type=content_type,
            )
            raw_path = self.storage.save(
                workspace_id=workspace_id,
                source_id=source.id,
                content=resource.content,
                extension=extension,
                text=document.content_text,
                metadata={
                    **document.metadata,
                    "content_type": content_type,
                    "final_url": resource.final_url,
                    "http_status": resource.status_code,
                },
            )

            status = (
                SourceStatus.NEEDS_OCR
                if any("OCR" in warning for warning in document.warnings)
                else SourceStatus.READY
            )
            updated = self.source_repository.update(
                source.id,
                title=document.title or title_hint,
                final_url=resource.final_url or None,
                content_type=content_type,
                source_kind=source_kind,
                status=status,
            )
            self.source_repository.save_snapshot(
                source.id,
                raw_path=raw_path,
                content_text=document.content_text,
                segments=[
                    segment.model_dump(mode="json")
                    for segment in document.segments
                ],
                metadata=document.metadata,
                warnings=document.warnings,
                page_count=document.page_count,
                http_status=resource.status_code,
            )
        except (HtmlExtractionError, PdfExtractionError, StorageError, OSError) as exc:
            self.source_repository.update_status(
                source.id,
                SourceStatus.FAILED,
                error=str(exc),
            )
            raise SourceIngestionError(str(exc)) from exc
        except Exception as exc:
            self.source_repository.update_status(
                source.id,
                SourceStatus.FAILED,
                error=str(exc),
            )
            raise

        children: list[Source] = []
        warnings = list(document.warnings)
        if follow_pdfs and content_type in {"text/html", "application/xhtml+xml"}:
            links = _find_pdf_links(resource.content, resource.final_url)
            limit = max_links if max_links is not None else self.settings.max_linked_pdfs
            for link in links[: max(0, limit)]:
                try:
                    child = self.add_url(
                        workspace_id,
                        link,
                        use_browser=False,
                        follow_pdfs=False,
                        parent_source_id=source.id,
                    )
                    children.append(child.source)
                    warnings.extend(child.warnings)
                except Exception as exc:  # noqa: BLE001
                    warnings.append(
                        f"Falha ao ingerir PDF vinculado {link}: {exc}"
                    )

        return IngestionResult(
            source=updated,
            children=children,
            warnings=warnings,
        )

    # Escolhe o extrator correto e devolve o documento e a extensão.
    def _extract_document(
        self,
        *,
        resource: FetchedResource,
        content_type: str,
    ) -> tuple[ExtractedDocument, str]:
        if is_pdf_resource(resource.content, content_type):
            return (
                self.pdf_extractor.extract(resource.content, resource.final_url),
                ".pdf",
            )
        return (
            self.html_extractor.extract(resource.content, resource.final_url),
            ".html",
        )


# Determina o Content-Type de um arquivo local.
def _content_type_for_file(path: Path, content: bytes) -> str:
    if content.startswith(b"%PDF-") or path.suffix.lower() == ".pdf":
        return "application/pdf"

    if path.suffix.lower() in {".html", ".htm"}:
        return "text/html"

    declared = detect_content_type(content, None)
    if declared:
        return declared
    raise SourceIngestionError(
        f"Formato não suportado para '{path.name}'. Use HTML ou PDF."
    )


# Extrai links de PDF do mesmo domínio.
def _find_pdf_links(content: bytes, base_url: str) -> list[str]:
    if not base_url:
        return []

    soup = BeautifulSoup(content, "lxml")
    base_host = (urlparse(base_url).hostname or "").lower()
    links: list[str] = []

    for anchor in soup.find_all("a", href=True):
        target = urljoin(base_url, str(anchor["href"]).strip())
        parsed = urlparse(target)
        if parsed.scheme not in {"http", "https"}:
            continue
        if (parsed.hostname or "").lower() != base_host:
            continue
        if not parsed.path.lower().endswith(".pdf"):
            continue
        normalized = parsed._replace(fragment="").geturl()
        if normalized not in links:
            links.append(normalized)

    return links
