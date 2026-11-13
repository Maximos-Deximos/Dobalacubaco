# Testes da ajuda central da CLI.

from app.main import main
from app.ui.help import render_help


# Exibe a ajuda geral sem argumentos.
def test_help_main_outputs_overview(capsys) -> None:
    assert main(["help"]) == 0

    output = capsys.readouterr().out
    assert "Agente de Editais" in output
    assert "Áreas de trabalho" in output
    assert "proposal new" in output
    assert "tui" in output


# Exibe detalhes de um subcomando.
def test_help_main_outputs_command_details(capsys) -> None:
    assert main(["help", "proposal", "new"]) == 0

    output = capsys.readouterr().out
    assert "proposal new" in output
    assert "Uso: proposal new" in output
    assert "--workspace" in output


# Agrupa subcomandos quando o tópico é um grupo.
def test_help_group_lists_subcommands(capsys) -> None:
    assert main(["help", "proposal"]) == 0

    output = capsys.readouterr().out
    assert "proposal list" in output
    assert "proposal outline" in output


# Retorna código 2 para um tópico desconhecido.
def test_help_unknown_topic(capsys) -> None:
    assert main(["help", "desconhecido"]) == 2

    captured = capsys.readouterr()
    assert "não encontrado" in captured.err


# O renderizador é compartilhado com a TUI.
def test_render_help_all_contains_implemented_commands() -> None:
    output = render_help(show_all=True)

    assert "help —" in output
    assert "tui —" in output
    assert "proposal show —" in output
