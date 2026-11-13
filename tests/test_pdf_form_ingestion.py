# Testes de inspeção e preenchimento de campos AcroForm.

from io import BytesIO

import pytest
from pypdf import PdfReader

from app.ingestion.pdf_form import PdfFormError, PdfFormFiller, PdfFormInspector
from app.schemas.pdf import PdfFieldType
from tests.pdf_helpers import PDF_FIXTURE


# Lê os campos textuais, checkbox e radio do PDF de teste.
def test_inspects_acroform_fields() -> None:
    inspected = PdfFormInspector().inspect(PDF_FIXTURE.read_bytes())

    fields = {field.field_name: field for field in inspected.fields}
    assert inspected.page_count == 1
    assert inspected.warnings == []
    assert set(fields) == {"full_name", "email", "city", "agree", "gender"}
    assert fields["full_name"].field_type == PdfFieldType.TEXT
    assert fields["full_name"].label == "Nome completo"
    assert fields["full_name"].page_number == 1
    assert fields["agree"].field_type == PdfFieldType.CHECKBOX
    assert [option.value for option in fields["agree"].options] == ["Yes"]
    assert fields["gender"].field_type == PdfFieldType.RADIO
    assert [option.value for option in fields["gender"].options] == ["M", "F"]
    assert fields["gender"].current_value == "M"


# Rejeita PDFs sem AcroForm.
def test_rejects_pdf_without_form() -> None:
    content = (PDF_FIXTURE.parent / "sample_edital.pdf").read_bytes()

    with pytest.raises(PdfFormError, match="AcroForm"):
        PdfFormInspector().inspect(content)


# Preenche texto e botões sem alterar o conteúdo original.
def test_fills_fields_and_preserves_original() -> None:
    original = PDF_FIXTURE.read_bytes()
    filled = PdfFormFiller().fill(
        original,
        {
            "full_name": "Fulano de Tal",
            "agree": "Yes",
            "gender": "F",
        },
    )

    assert PDF_FIXTURE.read_bytes() == original
    fields = PdfReader(BytesIO(filled)).get_fields() or {}
    assert fields["full_name"]["/V"] == "Fulano de Tal"
    assert fields["agree"]["/V"] == "/Yes"
    assert fields["gender"]["/V"] == "/F"


# Rejeita preenchimento sem valores.
def test_filler_requires_values() -> None:
    with pytest.raises(PdfFormError, match="Nenhum valor"):
        PdfFormFiller().fill(PDF_FIXTURE.read_bytes(), {})
