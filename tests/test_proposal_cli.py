# Testes dos comandos de proposta e da abertura padrão da TUI.

import json

import app.main as main_module
from app.application.proposal_service import ProposalService
from app.application.workspace_service import WorkspaceService
from app.main import main
from app.memory.database import init_db


# Abre a TUI quando a CLI é chamada sem argumentos.
def test_main_without_args_opens_tui(monkeypatch) -> None:
    calls: list[bool] = []

    def fake_open_tui() -> int:
        calls.append(True)
        return 0

    monkeypatch.setattr(main_module, "_open_tui", fake_open_tui)

    assert main([]) == 0
    assert calls == [True]


# O subcomando tui usa o mesmo ponto de entrada.
def test_tui_command_opens_tui(monkeypatch) -> None:
    calls: list[bool] = []

    def fake_open_tui() -> int:
        calls.append(True)
        return 0

    monkeypatch.setattr(main_module, "_open_tui", fake_open_tui)

    assert main(["tui"]) == 0
    assert calls == [True]


# Cria e lista propostas pela CLI.
def test_proposal_cli_flow(isolated_database: str, capsys) -> None:
    init_db(isolated_database)
    workspace = WorkspaceService().create("Workspace CLI", "")

    assert (
        main(
            [
                "proposal",
                "new",
                "--workspace",
                str(workspace.id),
                "--title",
                "Proposta CLI",
                "--description",
                "Descrição",
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "Proposta 'Proposta CLI' criada" in output

    assert main(["proposal", "list"]) == 0
    output = capsys.readouterr().out
    assert "Proposta CLI" in output

    assert main(["proposal", "outline", "1"]) == 0
    output = capsys.readouterr().out
    assert "Resumo [resumo]" in output


# Emite JSON quando solicitado.
def test_proposal_cli_json_output(isolated_database: str, capsys) -> None:
    init_db(isolated_database)
    workspace = WorkspaceService().create("Workspace JSON", "")
    proposal = ProposalService().create(workspace.id, "Proposta JSON")

    assert main(["proposal", "show", str(proposal.id), "--json"]) == 0

    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["id"] == proposal.id
    assert payload["title"] == "Proposta JSON"
    assert len(payload["sections"]) == 9


# Informa erro de workspace inexistente.
def test_proposal_cli_reports_missing_workspace(
    isolated_database: str,
    capsys,
) -> None:
    init_db(isolated_database)

    assert (
        main(
            [
                "proposal",
                "new",
                "--workspace",
                "999",
                "--title",
                "Sem workspace",
            ]
        )
        == 1
    )

    assert "não encontrada" in capsys.readouterr().err
