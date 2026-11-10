# Testes de integração dos comandos de perfil da CLI.

import json

from app.main import main


# Executa o fluxo completo de criação, atualização e leitura.
def test_profile_cli_flow(isolated_database, capsys) -> None:
    assert main(["profile", "init"]) == 0
    assert "criado" in capsys.readouterr().out

    assert main(
        [
            "profile",
            "set",
            "full_name=Mizera Gorda",
            "email=mizera@mizera.com",
            "custom.team_name=Gulosos.com",
        ]
    ) == 0
    assert "atualizado" in capsys.readouterr().out

    assert main(["profile", "show", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["full_name"] == "Mizera Gorda"
    assert payload["email"] == "mizera@mizera.com"
    assert payload["custom_answers"]["team_name"] == "Gulosos.com"


# Confere que init não sobrescreve um perfil existente.
def test_profile_init_is_idempotent(isolated_database, capsys) -> None:
    assert main(["profile", "init"]) == 0
    capsys.readouterr()

    assert main(["profile", "init"]) == 0
    assert "já existe" in capsys.readouterr().out


# Rejeita chaves desconhecidas sem alterar o perfil.
def test_profile_set_rejects_unknown_key(isolated_database, capsys) -> None:
    assert main(["profile", "init"]) == 0
    capsys.readouterr()

    assert main(["profile", "set", "unknown=valor"]) == 2
    assert "Chave desconhecida" in capsys.readouterr().err


# Informa quando ainda não existe perfil.
def test_profile_show_without_profile(isolated_database, capsys) -> None:
    assert main(["profile", "show"]) == 1
    assert "Nenhum perfil cadastrado" in capsys.readouterr().err
