# Testes dos repositórios de sessões PDF e memória vetorial.

from app.memory.database import init_db
from app.memory.pdf_form_repository import PdfFormRepository, PdfMemoryRepository
from app.schemas.pdf import (
    PdfFieldStatus,
    PdfFieldType,
    PdfFormField,
    PdfSessionStatus,
)
from tests.pdf_helpers import create_pdf_source


# Cria uma sessão com campos e exercita a revisão otimista.
def test_session_and_field_lifecycle(isolated_database: str) -> None:
    init_db(isolated_database)
    workspace_id, source = create_pdf_source()
    repository = PdfFormRepository(isolated_database)
    fields = [
        PdfFormField(
            field_name="full_name",
            label="Nome completo",
            field_type=PdfFieldType.TEXT,
        ),
        PdfFormField(
            field_name="agree",
            label="Aceite",
            field_type=PdfFieldType.CHECKBOX,
            options=[],
        ),
    ]

    created = repository.create_session(
        workspace_id=workspace_id,
        source_id=source.id,
        instructions="Preencha com atenção.",
        fields=fields,
    )

    assert created.id == 1
    assert created.status == PdfSessionStatus.DRAFT
    assert len(created.fields) == 2
    assert repository.find_latest_open(source.id).id == created.id

    updated = repository.update_field(
        created.id,
        "full_name",
        final_value="Fulano",
        status=PdfFieldStatus.EDITED,
        increment_revision=True,
    )
    assert updated is not None
    assert updated.revision == 1
    assert updated.final_value == "Fulano"

    stale = repository.update_field(
        created.id,
        "full_name",
        expected_revision=0,
        final_value="Outro",
    )
    assert stale is None

    repository.mark_filled(
        created.id,
        output_path="/tmp/preenchido.pdf",
        field_names=["full_name"],
    )
    filled = repository.get_session(created.id)
    assert filled.status == PdfSessionStatus.FILLED
    assert filled.output_path == "/tmp/preenchido.pdf"
    assert repository.find_latest_open(source.id) is None
    assert repository.find_latest(source.id).id == created.id


# Insere, incrementa e lista memórias com e sem embedding.
def test_memory_upsert_and_listing(isolated_database: str) -> None:
    init_db(isolated_database)
    workspace_id, source = create_pdf_source()
    repository = PdfMemoryRepository(isolated_database)

    first = repository.upsert(
        workspace_id=workspace_id,
        source_id=source.id,
        label="Nome completo",
        field_name="full_name",
        field_type="text",
        value="Fulano",
        embedding=[1.0, 0.0],
        embedding_model="fake",
    )
    second = repository.upsert(
        workspace_id=workspace_id,
        source_id=source.id,
        label="Nome completo",
        field_name="full_name",
        field_type="text",
        value="Fulano",
        embedding=[1.0, 0.0],
        embedding_model="fake",
    )
    repository.upsert(
        workspace_id=workspace_id,
        source_id=source.id,
        label="Cidade",
        field_name="city",
        field_type="text",
        value="Recife",
        embedding=None,
        embedding_model=None,
    )

    assert second.id == first.id
    assert second.usage_count == 2
    assert repository.count_by_workspace(workspace_id) == (2, 1)
    embedded = repository.list_by_workspace(workspace_id, only_embedded=True)
    assert len(embedded) == 1
    assert embedded[0].value == "Fulano"
