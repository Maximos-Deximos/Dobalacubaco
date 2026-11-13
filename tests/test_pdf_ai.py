# Testes do prompt e do parser de sugestões de PDF.

import json

import pytest

from app.ai.promts import (
    SYSTEM_PDF_SUGGESTION_PROMPT,
    build_pdf_suggestion_messages,
)
from app.ai.response_parser import PdfSuggestionParseError, parse_pdf_suggestions
from app.schemas.pdf import PdfFieldOption, PdfFieldType, PdfFormField


# Monta um campo de teste.
def _field(
    name: str,
    *,
    field_type: PdfFieldType = PdfFieldType.TEXT,
    options: list[PdfFieldOption] | None = None,
    max_length: int | None = None,
) -> PdfFormField:
    return PdfFormField(
        field_name=name,
        label=name.replace("_", " ").title(),
        field_type=field_type,
        options=options or [],
        max_length=max_length,
    )


# Valida o prompt e o conteúdo enviado ao modelo.
def test_builds_pdf_suggestion_messages() -> None:
    field = _field(
        "gender",
        field_type=PdfFieldType.RADIO,
        options=[
            PdfFieldOption(label="Masculino", value="M"),
            PdfFieldOption(label="Feminino", value="F"),
        ],
    )
    messages = build_pdf_suggestion_messages(
        [field],
        {"full_name": "Ana"},
        instructions="Use dados do edital.",
    )

    assert messages[0].content == SYSTEM_PDF_SUGGESTION_PROMPT
    assert "Ana" in messages[-1].content
    assert "gender" in messages[-1].content
    assert "Masculino" in messages[-1].content
    assert "Use dados do edital." in messages[-1].content


# Normaliza JSON, booleanos, listas, opções e limites.
def test_parses_and_normalizes_suggestions() -> None:
    fields = [
        _field("name", max_length=5),
        _field("agree", field_type=PdfFieldType.CHECKBOX),
        _field("gender", field_type=PdfFieldType.RADIO, options=[
            PdfFieldOption(label="M", value="M"),
            PdfFieldOption(label="F", value="F"),
        ]),
    ]
    raw = """```json
    {"suggestions": [
      {"field_name": "name", "value": "Fulano de Tal", "confidence": 2},
      {"field_name": "agree", "value": true, "confidence": "0.7"},
      {"field_name": "gender", "value": "X", "confidence": 0.5}
    ]}
    ```"""

    suggestions, warnings = parse_pdf_suggestions(raw, fields)

    values = {suggestion.field_name: suggestion.value for suggestion in suggestions}
    assert values == {"name": "Fulan", "agree": "Yes"}
    assert suggestions[0].confidence == 1.0
    assert any("truncado" in warning for warning in warnings)
    assert any("inválido" in warning for warning in warnings)


# Ignora campos desconhecidos, duplicados e somente leitura.
def test_parser_warns_about_invalid_fields() -> None:
    fields = [
        _field("name"),
        PdfFormField(
            field_name="locked",
            label="Locked",
            readonly=True,
        ),
    ]
    raw = json.dumps(
        {
            "suggestions": [
                {"field_name": "missing", "value": "x"},
                {"field_name": "locked", "value": "x"},
                {"field_name": "name", "value": "Ana"},
                {"field_name": "name", "value": "Bia"},
            ]
        }
    )

    suggestions, warnings = parse_pdf_suggestions(raw, fields)

    assert [suggestion.field_name for suggestion in suggestions] == ["name"]
    assert any("desconhecido" in warning for warning in warnings)
    assert any("não pode ser preenchido" in warning for warning in warnings)
    assert any("duplicada" in warning for warning in warnings)


# Rejeita respostas sem JSON ou sem a lista de sugestões.
def test_parser_rejects_invalid_json() -> None:
    with pytest.raises(PdfSuggestionParseError):
        parse_pdf_suggestions("sem json", [_field("name")])
    with pytest.raises(PdfSuggestionParseError):
        parse_pdf_suggestions('{"foo": []}', [_field("name")])
