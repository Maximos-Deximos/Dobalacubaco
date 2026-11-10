# Testes de inspeção e detecção de campos em páginas HTTPS simuladas.

import pytest

from app.browser.form_detector import FormDetector
from app.browser.page_inspector import PageInspector
from app.schemas.form import FieldType


# Confere a detecção dos principais tipos de campo do formulário.
@pytest.mark.browser
async def test_detects_hackathon_fields(forms_page) -> None:
    inspector = PageInspector()
    snapshot = await inspector.navigate(
        forms_page,
        "https://forms.test/hackathon.html",
    )

    assert snapshot.title == "Inscrição Hackathon"
    assert snapshot.form_count == 1

    result = await FormDetector().detect(forms_page, snapshot)
    by_name = {
        field.name: field for field in result.fields if field.name
    }

    assert by_name["full_name"].label == "Nome completo"
    assert by_name["full_name"].field_type == FieldType.TEXT
    assert by_name["full_name"].required is True
    assert by_name["email"].field_type == FieldType.EMAIL
    assert by_name["phone"].field_type == FieldType.TEL
    assert by_name["age"].field_type == FieldType.NUMBER
    assert by_name["birth_date"].field_type == FieldType.DATE
    assert by_name["organization"].label == "Organização"
    assert by_name["project"].field_type == FieldType.TEXTAREA

    track = by_name["track"]
    assert track.field_type == FieldType.SELECT
    assert "Inteligência Artificial" in track.options
    assert "" not in track.options

    experience = by_name["experience"]
    assert experience.field_type == FieldType.RADIO
    assert experience.options == [
        "Iniciante",
        "Intermediário",
        "Avançado",
    ]

    skills = by_name["skills"]
    assert skills.field_type == FieldType.CHECKBOX
    assert skills.options == [
        "Python",
        "JavaScript",
        "Design",
        "Hardware",
    ]

    consent = by_name["consent"]
    assert consent.field_type == FieldType.CONSENT
    assert consent.required is True

    assert by_name["disabled_field"].disabled is True
    assert by_name["readonly_field"].readonly is True
    assert all(field.input_type != "hidden" for field in result.fields)
    assert all(
        field.field_type != FieldType.UNKNOWN
        for field in result.fields
        if field.input_type != "file"
    )


# Confere aviso para campos de arquivo não suportados.
@pytest.mark.browser
async def test_warns_about_file_field(forms_page) -> None:
    inspector = PageInspector()
    snapshot = await inspector.navigate(
        forms_page,
        "https://forms.test/hackathon.html",
    )
    result = await FormDetector().detect(forms_page, snapshot)

    upload = next(field for field in result.fields if field.name == "upload")
    assert upload.field_type == FieldType.UNKNOWN
    assert any("arquivo" in warning.lower() for warning in result.warnings)


# Confere a detecção em um formulário com campos agrupados diferentes.
@pytest.mark.browser
async def test_detects_robotics_fields(forms_page) -> None:
    inspector = PageInspector()
    snapshot = await inspector.navigate(
        forms_page,
        "https://forms.test/robotics.html",
    )
    result = await FormDetector().detect(forms_page, snapshot)
    by_name = {
        field.name: field for field in result.fields if field.name
    }

    assert snapshot.title == "Inscrição Competição de Robótica"
    assert by_name["team_name"].required is True
    assert by_name["team_size"].field_type == FieldType.NUMBER
    assert by_name["category"].field_type == FieldType.SELECT
    assert by_name["autonomous"].field_type == FieldType.RADIO
    assert by_name["components"].field_type == FieldType.CHECKBOX
    assert by_name["safety_consent"].field_type == FieldType.CONSENT
    assert by_name["mentor_email"].field_type == FieldType.EMAIL

    field_ids = [field.field_id for field in result.fields]
    selectors = [field.selector for field in result.fields]
    assert len(field_ids) == len(set(field_ids))
    assert len(selectors) == len(set(selectors))


# Garante que uma página sem campos retorna lista vazia e aviso.
@pytest.mark.browser
async def test_page_without_fields(forms_page) -> None:
    await forms_page.set_content("<html><body><h1>Sem formulário</h1></body></html>")

    inspector = PageInspector()
    snapshot = await inspector.inspect(forms_page)
    result = await FormDetector().detect(forms_page, snapshot)

    assert result.fields == []
    assert any("Nenhum campo" in warning for warning in result.warnings)
