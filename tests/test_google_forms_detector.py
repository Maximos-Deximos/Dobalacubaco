# Testes do adaptador específico de Google Forms.

import pytest

from app.browser.form_detector import FormDetector
from app.browser.page_inspector import PageInspector
from app.main import build_parser
from app.schemas.form import FieldType
from app.ui.browser_cli import _print_debug

GOOGLE_FORM_URL = "https://docs.google.com/forms/d/e/teste/viewform"
EMBEDDED_URL = "https://forms.test/google_embedded.html"


# Executa a inspeção padrão do fixture do Google Forms.
async def _inspect(page, url: str):
    snapshot = await PageInspector().navigate(page, url)
    result = await FormDetector().detect(page, snapshot)
    return result


# Confere rótulos, tipos, opções e metadados das perguntas do Google Forms.
@pytest.mark.browser
async def test_detects_google_forms_questions(google_forms_page) -> None:
    result = await _inspect(google_forms_page, GOOGLE_FORM_URL)
    by_label = {field.label: field for field in result.fields}

    assert result.page.is_google_form is True
    assert result.page.form_title == "Edital de Inovação"
    assert result.page.section_title == "Dados do proponente"
    assert result.page.has_next is True
    assert result.page.form_count == 1
    assert GOOGLE_FORM_URL in result.page.inspected_frames

    name = by_label["Nome completo"]
    assert name.field_type == FieldType.TEXT
    assert name.required is True
    assert name.required_source == "native"
    assert name.adapter == "google_forms"
    assert name.frame_url == GOOGLE_FORM_URL
    assert "documento oficial" in name.help_text

    project = by_label["Resumo do projeto"]
    assert project.field_type == FieldType.TEXTAREA
    assert project.required is True
    assert project.label != "Sua resposta"

    previous = by_label["A equipe já participou de outra edição?"]
    assert previous.field_type == FieldType.RADIO
    assert previous.required is True
    assert previous.required_source == "data-required"
    assert previous.options == ["Sim", "Não"]
    assert previous.option_values == ["sim", "nao"]

    technologies = by_label["Tecnologias utilizadas"]
    assert technologies.field_type == FieldType.CHECKBOX
    assert technologies.required is True
    assert technologies.options == ["Python", "Arduino", "Raspberry Pi"]

    category = by_label["Categoria do edital"]
    assert category.field_type == FieldType.SELECT
    assert category.required is True
    assert category.options == ["Solução digital", "Robótica", "Saúde"]
    assert category.option_values == ["digital", "robotica", "saude"]

    maturity = by_label["Nível de maturidade"]
    assert maturity.field_type == FieldType.RADIO
    assert maturity.required is False
    assert maturity.options == ["1", "2", "3", "4", "5"]

    submission_date = by_label["Data de submissão"]
    assert submission_date.field_type == FieldType.DATE
    assert submission_date.required is True
    assert len(submission_date.subfields) == 3
    assert [part.label for part in submission_date.subfields] == [
        "DD",
        "MM",
        "YYYY",
    ]

    preferred_time = by_label["Horário preferencial"]
    assert preferred_time.field_type == FieldType.TIME
    assert len(preferred_time.subfields) == 2
    assert [part.label for part in preferred_time.subfields] == ["HH", "MM"]

    attachment = by_label["Anexo do projeto"]
    assert attachment.field_type == FieldType.FILE
    assert attachment.input_type == "file"
    assert any("arquivo" in warning.lower() for warning in result.warnings)

    grid = by_label["Avaliação por critério"]
    assert grid.field_type == FieldType.GRID
    assert grid.required is True
    assert grid.options == ["Atende", "Não atende"]
    assert [row.label for row in grid.subfields] == [
        "Clareza",
        "Viabilidade",
    ]
    assert all(len(row.options) == 2 for row in grid.subfields)

    consent = by_label["Concordo com os termos"]
    assert consent.field_type == FieldType.CONSENT
    assert consent.required is True
    assert consent.options == [
        "Concordo com os termos e a política de privacidade"
    ]

    field_ids = [field.field_id for field in result.fields]
    selectors = [field.selector for field in result.fields]
    assert len(field_ids) == len(set(field_ids))
    assert len(selectors) == len(set(selectors))
    assert all("sentinel" not in field.selector for field in result.fields)
    assert any("mais de uma seção" in warning for warning in result.warnings)


# Confere que o modo de debug mostra os detalhes dos campos detectados.
@pytest.mark.browser
async def test_debug_output_shows_detected_fields(
    google_forms_page,
    capsys,
) -> None:
    result = await _inspect(google_forms_page, GOOGLE_FORM_URL)
    _print_debug(result)
    output = capsys.readouterr().out

    assert "=== Modo debug do inspetor ===" in output
    assert "Campos detectados: 11" in output
    assert "Rótulo: Nome completo" in output
    assert "Seletor:" in output
    assert "Opções:" in output
    assert "Subcampos:" in output


# Confere que a CLI aceita o modo de debug no subcomando inspect.
def test_inspect_parser_accepts_debug_flag() -> None:
    args = build_parser().parse_args(
        ["inspect", "https://example.com", "--debug"]
    )

    assert args.debug_output is True


# Confere a inspeção de um Google Forms embutido em iframe.
@pytest.mark.browser
async def test_detects_google_forms_inside_iframe(
    embedded_google_form_page,
) -> None:
    result = await _inspect(embedded_google_form_page, EMBEDDED_URL)
    by_label = {field.label: field for field in result.fields}

    assert result.page.is_google_form is True
    assert result.page.form_count == 1
    assert GOOGLE_FORM_URL in result.page.inspected_frames
    assert "Nome completo" in by_label
    assert by_label["Nome completo"].frame_url == GOOGLE_FORM_URL
    assert by_label["Nome completo"].adapter == "google_forms"
    assert any("iframes" in warning for warning in result.warnings)
