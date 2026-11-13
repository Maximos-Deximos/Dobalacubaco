# Testes de integração dos comandos de fontes.

import json
from pathlib import Path

from app.main import main

FIXTURES = Path(__file__).parent / "fixtures" / "ingestion"


# Executa o fluxo de criação de workspace e ingestão de PDF.
def test_source_cli_add_file_and_show(isolated_database, capsys) -> None:
    assert main(["workspace", "new", "Edital CLI"]) == 0
    capsys.readouterr()

    assert main(
        [
            "source",
            "add-file",
            str(FIXTURES / "sample_edital.pdf"),
            "--workspace",
            "1",
        ]
    ) == 0
    output = capsys.readouterr().out
    assert "ingerida com status 'ready'" in output

    assert main(["source", "list", "--workspace", "1", "--json"]) == 0
    sources = json.loads(capsys.readouterr().out)
    assert sources[0]["source_kind"] == "uploaded_pdf"
    assert sources[0]["status"] == "ready"

    assert main(["source", "show", "1", "--json"]) == 0
    detail = json.loads(capsys.readouterr().out)
    assert detail["snapshot"]["page_count"] == 1
    assert "Edital de Inovacao 2026" in detail["snapshot"]["content_text"]


# Informa quando o workspace não existe.
def test_source_cli_missing_workspace(isolated_database, capsys) -> None:
    assert main(
        [
            "source",
            "add-file",
            str(FIXTURES / "sample_edital.pdf"),
            "--workspace",
            "99",
        ]
    ) == 1
    assert "Área de trabalho 99 não encontrada" in capsys.readouterr().err
