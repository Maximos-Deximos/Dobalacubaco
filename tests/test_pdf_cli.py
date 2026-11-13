# Testes de integração dos comandos de PDF da CLI.

import json
from pathlib import Path

from app.config import get_settings
from app.main import main
from app.memory.database import init_db
from tests.pdf_helpers import PDF_FIXTURE, FakePdfClient, create_pdf_source


# Prepara o serviço falso e uma sessão já sugerida.
def _prepare_session(isolated_database: str, monkeypatch) -> int:
    init_db(isolated_database)
    _workspace_id, source = create_pdf_source()
    monkeypatch.setenv("OLLAMA_EMBED_MODEL", "fake")
    get_settings.cache_clear()

    from app.application.pdf_form_service import PdfFormService

    service = PdfFormService(settings=get_settings(), client=FakePdfClient())
    session = service.open_session(source.id)
    list(service.suggest_live(session.id))
    service.approve_all(session.id)
    return session.id


# Lista os campos AcroForm em JSON.
def test_pdf_fields_cli(isolated_database: str, capsys) -> None:
    init_db(isolated_database)
    _workspace_id, source = create_pdf_source()

    assert main(["pdf", "fields", "--source", str(source.id), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["source_id"] == source.id
    assert len(payload["fields"]) == 5
    assert payload["fields"][0]["field_name"] == "full_name"


# Edita, aprova e preenche a sessão pela CLI.
def test_pdf_set_approve_and_fill_cli(
    isolated_database: str,
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    session_id = _prepare_session(isolated_database, monkeypatch)

    assert main(
        [
            "pdf",
            "set",
            str(session_id),
            "city",
            "Olinda",
            "--approve",
        ]
    ) == 0
    assert "Olinda" in capsys.readouterr().out

    assert main(["pdf", "approve", str(session_id), "--all"]) == 0
    assert "Sessão" in capsys.readouterr().out

    output = tmp_path / "saida.pdf"
    assert main(
        [
            "pdf",
            "fill",
            str(session_id),
            "--output",
            str(output),
            "--json",
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)

    assert output.is_file()
    assert payload["fields_filled"] == 5
    assert payload["output_path"] == str(output.resolve())
    assert PDF_FIXTURE.read_bytes() != output.read_bytes()


# Aplica valores de um arquivo JSON antes de preencher.
def test_pdf_fill_with_values_file(
    isolated_database: str,
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    session_id = _prepare_session(isolated_database, monkeypatch)
    values = tmp_path / "valores.json"
    values.write_text(json.dumps({"city": "Olinda"}), encoding="utf-8")
    output = tmp_path / "saida.pdf"

    assert main(
        [
            "pdf",
            "fill",
            str(session_id),
            "--output",
            str(output),
            "--values",
            str(values),
        ]
    ) == 0
    assert "Campos preenchidos: 5" in capsys.readouterr().out
