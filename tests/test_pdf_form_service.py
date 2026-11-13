# Testes do fluxo de sugestões, revisão e preenchimento de PDFs.

from pathlib import Path

import pytest
from pypdf import PdfReader

from app.application.pdf_form_service import PdfFormService, PdfFormServiceError
from app.config import get_settings
from app.memory.database import init_db
from app.memory.user_repository import UserRepository
from app.schemas.pdf import (
    PdfFieldStatus,
    PdfGenerationStatus,
    PdfSessionStatus,
    PdfSuggestionSource,
)
from app.schemas.profile import ProfileCreate
from tests.pdf_helpers import PDF_FIXTURE, FakePdfClient, create_pdf_source


# Monta o serviço com configuração isolada e cliente falso.
def _service(monkeypatch, client: FakePdfClient) -> PdfFormService:
    monkeypatch.setenv("OLLAMA_EMBED_MODEL", "fake")
    get_settings.cache_clear()
    return PdfFormService(
        settings=get_settings(),
        client=client,
        embedder=client,
    )


# Inspeciona a fonte e reutiliza a sessão aberta.
def test_inspects_source_and_reuses_session(isolated_database: str, monkeypatch) -> None:
    init_db(isolated_database)
    _workspace_id, source = create_pdf_source()
    service = _service(monkeypatch, FakePdfClient())

    inspection = service.inspect_source(source.id)
    assert inspection.source_id == source.id
    assert len(inspection.fields) == 5

    session = service.open_session(source.id)
    again = service.open_session(source.id)

    assert again.id == session.id
    assert len(session.fields) == 5
    assert session.status == PdfSessionStatus.DRAFT


# Gera lotes progressivos, aprova e preenche o PDF.
def test_suggests_approves_and_fills(
    isolated_database: str,
    monkeypatch,
    tmp_path: Path,
) -> None:
    init_db(isolated_database)
    workspace_id, source = create_pdf_source()
    client = FakePdfClient()
    service = _service(monkeypatch, client)
    session = service.open_session(source.id)

    batches = list(service.suggest_live(session.id))

    assert len(batches) >= 2
    assert batches[0].completed < batches[-1].completed
    assert batches[-1].done is True
    assert batches[-1].generation_status == PdfGenerationStatus.COMPLETED
    assert client.chat_calls >= 2

    detail = service.get_session(session.id)
    suggested = {field.field_name: field for field in detail.fields}
    assert suggested["full_name"].suggested_value == "Fulano de Tal"
    assert suggested["agree"].suggested_value == "Yes"
    assert suggested["gender"].suggested_value == "F"
    assert all(
        field.suggestion_source == PdfSuggestionSource.AI
        for field in detail.fields
    )

    approved = service.approve_all(session.id)
    assert approved.status == PdfSessionStatus.READY
    assert all(
        field.status == PdfFieldStatus.APPROVED for field in approved.fields
    )

    original = PDF_FIXTURE.read_bytes()
    output = tmp_path / "preenchido.pdf"
    result = service.fill(session.id, output)

    assert result.fields_filled == 5
    assert result.fields_skipped == 0
    assert output.is_file()
    assert PDF_FIXTURE.read_bytes() == original

    fields = PdfReader(str(output)).get_fields() or {}
    assert fields["full_name"]["/V"] == "Fulano de Tal"
    assert fields["email"]["/V"] == "fulano@example.com"
    assert fields["city"]["/V"] == "Recife"
    assert fields["agree"]["/V"] == "/Yes"
    assert fields["gender"]["/V"] == "/F"

    filled = service.get_session(session.id)
    assert filled.status == PdfSessionStatus.FILLED
    assert filled.output_path == str(output.resolve())
    assert service.memory_repository.count_by_workspace(workspace_id) == (5, 5)


# Reaproveita valores aprovados da memória vetorial em uma nova sessão.
def test_reuses_vector_memory_in_new_session(
    isolated_database: str,
    monkeypatch,
    tmp_path: Path,
) -> None:
    init_db(isolated_database)
    _workspace_id, source = create_pdf_source()
    client = FakePdfClient()
    service = _service(monkeypatch, client)

    first = service.open_session(source.id)
    list(service.suggest_live(first.id))
    service.approve_all(first.id)
    service.fill(first.id, tmp_path / "primeiro.pdf")

    second = service.open_session(source.id)
    client.chat_calls = 0
    batches = list(service.suggest_live(second.id))

    assert second.id != first.id
    assert client.chat_calls == 0
    assert batches[-1].done is True
    detail = service.get_session(second.id)
    assert all(
        field.suggestion_source == PdfSuggestionSource.VECTOR
        for field in detail.fields
    )
    assert {field.suggested_value for field in detail.fields} == {
        "Fulano de Tal",
        "fulano@example.com",
        "Recife",
        "Yes",
        "F",
    }


# Prioriza dados do perfil antes de chamar a IA.
def test_profile_suggestions_precede_ai(
    isolated_database: str,
    monkeypatch,
) -> None:
    init_db(isolated_database)
    _workspace_id, source = create_pdf_source()
    UserRepository().create(
        ProfileCreate(
            full_name="Ana Silva",
            email="ana@example.com",
            city="Natal",
        )
    )
    client = FakePdfClient()
    service = _service(monkeypatch, client)
    session = service.open_session(source.id)

    list(service.suggest_live(session.id))

    detail = service.get_session(session.id)
    fields = {field.field_name: field for field in detail.fields}
    assert fields["full_name"].suggested_value == "Ana Silva"
    assert fields["email"].suggested_value == "ana@example.com"
    assert fields["city"].suggested_value == "Natal"
    assert fields["full_name"].suggestion_source == PdfSuggestionSource.PROFILE
    sent = {field["field_name"] for batch in client.chat_payloads for field in batch}
    assert sent == {"agree", "gender"}


# Regenerar sugestões preserva valores editados manualmente.
def test_refresh_preserves_manual_edits(
    isolated_database: str,
    monkeypatch,
) -> None:
    init_db(isolated_database)
    _workspace_id, source = create_pdf_source()
    service = _service(monkeypatch, FakePdfClient())
    session = service.open_session(source.id)

    service.update_field_live(session.id, "full_name", "Nome Manual")
    list(service.suggest_live(session.id, refresh=True))

    detail = service.get_session(session.id)
    fields = {field.field_name: field for field in detail.fields}
    assert fields["full_name"].final_value == "Nome Manual"
    assert fields["full_name"].status == PdfFieldStatus.EDITED
    assert fields["city"].status == PdfFieldStatus.SUGGESTED


# Impede que o preenchimento sobrescreva o PDF original.
def test_fill_rejects_original_path(isolated_database: str, monkeypatch) -> None:
    init_db(isolated_database)
    _workspace_id, source = create_pdf_source()
    service = _service(monkeypatch, FakePdfClient())
    session = service.open_session(source.id)
    list(service.suggest_live(session.id))
    service.approve_all(session.id)
    raw_path = service.source_repository.get_detail(source.id).snapshot.raw_path

    with pytest.raises(PdfFormServiceError, match="original"):
        service.fill(session.id, raw_path)
