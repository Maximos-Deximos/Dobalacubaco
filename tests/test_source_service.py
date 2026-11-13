# Testes de integração do serviço de ingestão de fontes.

from pathlib import Path

import pytest

from app.application.source_service import (
    SourceIngestionError,
    SourceIngestionService,
)
from app.application.workspace_service import WorkspaceService
from app.config import get_settings
from app.ingestion.models import FetchedResource
from app.memory.database import init_db

FIXTURES = Path(__file__).parent / "fixtures" / "ingestion"


# Fetcher falso que devolve recursos pré-configurados por URL.
class FakeFetcher:
    def __init__(self, resources: dict[str, FetchedResource]) -> None:
        self.resources = resources
        self.calls: list[str] = []

    def fetch(self, url: str) -> FetchedResource:
        self.calls.append(url)
        return self.resources[url]


# Monta o serviço com banco e workspace isolados.
def make_service(resources: dict[str, FetchedResource]) -> tuple[SourceIngestionService, int]:
    init_db()
    workspace = WorkspaceService().create("Workspace de Teste")
    settings = get_settings()
    service = SourceIngestionService(
        settings=settings,
        http_fetcher=FakeFetcher(resources),
    )
    return service, workspace.id


# Ingere HTML público e persiste snapshot.
def test_add_url_html(isolated_database) -> None:
    resources = {
        "https://example.com/edital": FetchedResource(
            content=(FIXTURES / "sample_edital.html").read_bytes(),
            content_type="text/html",
            final_url="https://example.com/edital",
            status_code=200,
        )
    }
    service, workspace_id = make_service(resources)

    result = service.add_url(workspace_id, "https://example.com/edital")

    assert result.source.status.value == "ready"
    assert result.source.source_kind.value == "web_page"
    assert result.source.title == "Edital de Inovação 2026"

    detail = service.get_source(result.source.id)
    assert detail.snapshot is not None
    assert "Apoiar soluções digitais" in detail.snapshot.content_text
    assert Path(detail.snapshot.raw_path).is_file()


# Reaproveita a fonte quando o hash já foi ingerido.
def test_deduplicates_by_hash(isolated_database) -> None:
    resource = FetchedResource(
        content=(FIXTURES / "sample_edital.html").read_bytes(),
        content_type="text/html",
        final_url="https://example.com/edital",
        status_code=200,
    )
    service, workspace_id = make_service(
        {
            "https://example.com/edital": resource,
            "https://example.com/edital-2": resource,
        }
    )

    first = service.add_url(workspace_id, "https://example.com/edital")
    second = service.add_url(workspace_id, "https://example.com/edital-2")

    assert second.duplicate is True
    assert second.source.id == first.source.id
    assert len(service.list_sources(workspace_id)) == 1


# Ingere PDF local.
def test_add_file_pdf(isolated_database) -> None:
    service, workspace_id = make_service({})

    result = service.add_file(
        workspace_id,
        FIXTURES / "sample_edital.pdf",
    )

    assert result.source.status.value == "ready"
    assert result.source.source_kind.value == "uploaded_pdf"

    detail = service.get_source(result.source.id)
    assert detail.snapshot is not None
    assert detail.snapshot.page_count == 1
    assert "Edital de Inovacao 2026" in detail.snapshot.content_text


# PDF sem texto fica marcado para OCR.
def test_scanned_pdf_needs_ocr(isolated_database) -> None:
    service, workspace_id = make_service({})

    result = service.add_file(workspace_id, FIXTURES / "scanned.pdf")

    assert result.source.status.value == "needs_ocr"
    assert any("OCR" in warning for warning in result.warnings)


# Falha de extração registra status failed.
def test_extraction_failure_marks_source_failed(isolated_database) -> None:
    service, workspace_id = make_service(
        {
            "https://example.com/quebrado.pdf": FetchedResource(
                content=b"nao e um pdf",
                content_type="application/pdf",
                final_url="https://example.com/quebrado.pdf",
                status_code=200,
            )
        }
    )

    with pytest.raises(SourceIngestionError):
        service.add_url(workspace_id, "https://example.com/quebrado.pdf")

    sources = service.list_sources(workspace_id)
    assert len(sources) == 1
    assert sources[0].status.value == "failed"
    assert sources[0].error


# Segue links de PDF do mesmo domínio com limite.
def test_follows_pdf_links(isolated_database) -> None:
    first_pdf = FetchedResource(
        content=(FIXTURES / "sample_edital.pdf").read_bytes(),
        content_type="application/pdf",
        final_url="https://example.com/documentos/anexo-i.pdf",
        status_code=200,
    )
    service, workspace_id = make_service(
        {
            "https://example.com/edital": FetchedResource(
                content=(FIXTURES / "page_with_pdf_links.html").read_bytes(),
                content_type="text/html",
                final_url="https://example.com/edital",
                status_code=200,
            ),
            "https://example.com/documentos/anexo-i.pdf": first_pdf,
        }
    )

    result = service.add_url(
        workspace_id,
        "https://example.com/edital",
        follow_pdfs=True,
        max_links=1,
    )

    assert len(result.children) == 1
    assert result.children[0].source_kind.value == "web_pdf"
    assert result.children[0].parent_source_id == result.source.id
