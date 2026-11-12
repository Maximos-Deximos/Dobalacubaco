# Testes de integração dos comandos de workspace.

import json

from app.main import main


# Executa o fluxo de criação, listagem e exibição.
def test_workspace_cli_flow(isolated_database, capsys) -> None:
    assert main(
        [
            "workspace",
            "new",
            "Edital de Inovação",
            "--description",
            "Projeto teste",
        ]
    ) == 0
    assert "criado com sucesso" in capsys.readouterr().out

    assert main(["workspace", "list", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["name"] == "Edital de Inovação"
    assert payload[0]["description"] == "Projeto teste"

    assert main(["workspace", "show", "1", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["id"] == 1
    assert payload["status"] == "active"


# Rejeita nome duplicado com código de validação.
def test_workspace_cli_rejects_duplicate(isolated_database, capsys) -> None:
    assert main(["workspace", "new", "Duplicado"]) == 0
    capsys.readouterr()

    assert main(["workspace", "new", "Duplicado"]) == 2
    assert "Já existe" in capsys.readouterr().err


# Informa quando o workspace não existe.
def test_workspace_cli_missing(isolated_database, capsys) -> None:
    assert main(["workspace", "show", "999"]) == 1
    assert "não encontrado" in capsys.readouterr().err
