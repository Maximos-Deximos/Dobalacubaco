# Ponto de entrada da CLI do agente.

from __future__ import annotations

import argparse
import sys

from app.application.diagnostics_service import (
    check_ollama as _check_ollama_impl,
)
from app.application.diagnostics_service import run_diagnostics
from app.config import get_settings
from app.logging_config import configure_logging
from app.ui.browser_cli import command_inspect
from app.ui.chat_cli import (
    command_chat_ask,
    command_chat_repl,
    command_chat_status,
)
from app.ui.cli import (
    command_profile_init,
    command_profile_set,
    command_profile_show,
)
from app.ui.help_cli import command_help
from app.ui.pdf_cli import (
    command_pdf_approve,
    command_pdf_fields,
    command_pdf_fill,
    command_pdf_set,
    command_pdf_show,
    command_pdf_suggest,
)
from app.ui.proposal_cli import (
    command_proposal_list,
    command_proposal_new,
    command_proposal_outline,
    command_proposal_show,
)
from app.ui.source_cli import (
    command_source_add,
    command_source_add_file,
    command_source_index,
    command_source_list,
    command_source_show,
)
from app.ui.workspace_cli import (
    command_workspace_list,
    command_workspace_new,
    command_workspace_show,
)


# Mantém o nome histórico usado por testes e integrações.
def _check_ollama(
    host: str,
    timeout: int,
    model: str,
    embed_model: str,
) -> tuple[bool, str, bool, str]:
    return _check_ollama_impl(host, timeout, model, embed_model)


# Executa verificações básicas de instalação e configuração.
def command_doctor(_args: argparse.Namespace) -> int:
    checks = run_diagnostics(get_settings())

    failed = False
    for check in checks:
        status = "OK" if check.ok else "FALHA"
        if not check.ok:
            failed = True
        print(f"[{status:5}] {check.name}: {check.detail}")

    return 1 if failed else 0


# Abre a TUI em um import tardio para não pesar os comandos simples.
def _open_tui() -> int:
    from app.tui.app import run_tui

    return run_tui()


# Executa o subcomando explícito da TUI.
def command_tui(_args: argparse.Namespace) -> int:
    return _open_tui()


# Registra o subcomando de ajuda.
def _add_help_parser(subparsers: argparse._SubParsersAction) -> None:
    help_parser = subparsers.add_parser(
        "help",
        help="exibe a ajuda geral ou de um comando",
    )
    help_parser.add_argument(
        "topic",
        nargs="*",
        help="comando ou grupo de comandos",
    )
    help_parser.add_argument(
        "--all",
        action="store_true",
        dest="show_all",
        help="exibe a ajuda detalhada de todos os comandos",
    )
    help_parser.set_defaults(func=command_help)


# Registra o subcomando da interface de terminal.
def _add_tui_parser(subparsers: argparse._SubParsersAction) -> None:
    tui_parser = subparsers.add_parser(
        "tui",
        help="abre a interface de terminal",
    )
    tui_parser.set_defaults(func=command_tui)


# Registra os subcomandos de proposta.
def _add_proposal_parser(subparsers: argparse._SubParsersAction) -> None:
    proposal = subparsers.add_parser(
        "proposal",
        help="cria e consulta propostas de solução",
    )
    proposal_subparsers = proposal.add_subparsers(
        dest="proposal_command",
        required=True,
    )

    proposal_new = proposal_subparsers.add_parser(
        "new",
        help="cria uma proposta com a estrutura inicial",
    )
    proposal_new.add_argument(
        "--workspace",
        type=int,
        required=True,
        dest="workspace_id",
        help="ID do workspace",
    )
    proposal_new.add_argument(
        "--title",
        required=True,
        help="título da proposta",
    )
    proposal_new.add_argument(
        "--description",
        default="",
        help="descrição da proposta",
    )
    proposal_new.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="exibe o resultado em JSON",
    )
    proposal_new.set_defaults(func=command_proposal_new)

    proposal_list = proposal_subparsers.add_parser(
        "list",
        help="lista as propostas",
    )
    proposal_list.add_argument(
        "--workspace",
        type=int,
        default=None,
        dest="workspace_id",
        help="filtra por workspace",
    )
    proposal_list.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="exibe o resultado em JSON",
    )
    proposal_list.set_defaults(func=command_proposal_list)

    proposal_show = proposal_subparsers.add_parser(
        "show",
        help="exibe uma proposta e suas seções",
    )
    proposal_show.add_argument(
        "proposal_id",
        type=int,
        help="ID da proposta",
    )
    proposal_show.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="exibe o resultado em JSON",
    )
    proposal_show.set_defaults(func=command_proposal_show)

    proposal_outline = proposal_subparsers.add_parser(
        "outline",
        help="exibe o sumário de seções da proposta",
    )
    proposal_outline.add_argument(
        "proposal_id",
        type=int,
        help="ID da proposta",
    )
    proposal_outline.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="exibe o resultado em JSON",
    )
    proposal_outline.set_defaults(func=command_proposal_outline)


# Registra os subcomandos de perfil.
def _add_profile_parser(subparsers: argparse._SubParsersAction) -> None:
    profile = subparsers.add_parser(
        "profile",
        help="gerencia o perfil local",
    )
    profile_subparsers = profile.add_subparsers(
        dest="profile_command",
        required=True,
    )

    profile_init = profile_subparsers.add_parser(
        "init",
        help="cria o perfil padrão",
    )
    profile_init.set_defaults(func=command_profile_init)

    profile_show = profile_subparsers.add_parser(
        "show",
        help="exibe o perfil padrão",
    )
    profile_show.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="exibe o perfil em JSON",
    )
    profile_show.set_defaults(func=command_profile_show)

    profile_set = profile_subparsers.add_parser(
        "set",
        help="atualiza o perfil padrão",
    )
    profile_set.add_argument(
        "assignments",
        nargs="+",
        metavar="CHAVE=VALOR",
        help="campos no formato chave=valor",
    )
    profile_set.set_defaults(func=command_profile_set)


# Registra o subcomando de inspeção de formulários.
def _add_inspect_parser(subparsers: argparse._SubParsersAction) -> None:
    inspect_parser = subparsers.add_parser(
        "inspect",
        help="inspeciona os campos de formulário de uma URL HTTPS",
    )
    inspect_parser.add_argument(
        "url",
        help="URL HTTPS do formulário",
    )
    inspect_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="exibe o resultado em JSON",
    )
    inspect_parser.add_argument(
        "--debug",
        action="store_true",
        dest="debug_output",
        help="exibe todos os detalhes dos campos detectados",
    )
    inspect_parser.set_defaults(func=command_inspect)


# Registra os subcomandos de workspace.
def _add_workspace_parser(subparsers: argparse._SubParsersAction) -> None:
    workspace = subparsers.add_parser(
        "workspace",
        help="gerencia workspaces de editais",
    )
    workspace_subparsers = workspace.add_subparsers(
        dest="workspace_command",
        required=True,
    )

    workspace_new = workspace_subparsers.add_parser(
        "new",
        help="cria um workspace",
    )
    workspace_new.add_argument("name", help="nome do workspace")
    workspace_new.add_argument(
        "--description",
        default="",
        help="descrição do workspace",
    )
    workspace_new.set_defaults(func=command_workspace_new)

    workspace_list = workspace_subparsers.add_parser(
        "list",
        help="lista os workspaces",
    )
    workspace_list.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="exibe o resultado em JSON",
    )
    workspace_list.set_defaults(func=command_workspace_list)

    workspace_show = workspace_subparsers.add_parser(
        "show",
        help="exibe um workspace",
    )
    workspace_show.add_argument("workspace_id", type=int, help="ID do workspace")
    workspace_show.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="exibe o resultado em JSON",
    )
    workspace_show.set_defaults(func=command_workspace_show)


# Registra os subcomandos de fontes.
def _add_source_parser(subparsers: argparse._SubParsersAction) -> None:
    source = subparsers.add_parser(
        "source",
        help="adiciona e consulta fontes de editais",
    )
    source_subparsers = source.add_subparsers(
        dest="source_command",
        required=True,
    )

    source_add = source_subparsers.add_parser(
        "add",
        help="baixa e ingere uma URL pública",
    )
    source_add.add_argument("url", help="URL pública do edital ou documento")
    source_add.add_argument(
        "--workspace",
        type=int,
        required=True,
        dest="workspace_id",
        help="ID do workspace",
    )
    source_add.add_argument(
        "--browser",
        action="store_true",
        dest="use_browser",
        help="força o uso do Playwright para renderizar a página",
    )
    source_add.add_argument(
        "--follow-pdfs",
        action="store_true",
        dest="follow_pdfs",
        help="ingere também PDFs vinculados na página",
    )
    source_add.add_argument(
        "--max-links",
        type=int,
        default=None,
        help="limite de PDFs vinculados a ingerir",
    )
    source_add.set_defaults(func=command_source_add)

    source_add_file = source_subparsers.add_parser(
        "add-file",
        help="ingere um arquivo HTML ou PDF local",
    )
    source_add_file.add_argument("path", help="caminho do arquivo")
    source_add_file.add_argument(
        "--workspace",
        type=int,
        required=True,
        dest="workspace_id",
        help="ID do workspace",
    )
    source_add_file.set_defaults(func=command_source_add_file)

    source_index = source_subparsers.add_parser(
        "index",
        help="cria ou atualiza o índice de busca",
    )
    source_index.add_argument(
        "--workspace",
        type=int,
        required=True,
        dest="workspace_id",
        help="ID do workspace",
    )
    source_index.add_argument(
        "--source",
        type=int,
        default=None,
        dest="source_id",
        help="indexa apenas uma fonte",
    )
    source_index.add_argument(
        "--force",
        action="store_true",
        help="recria os trechos mesmo que já estejam indexados",
    )
    source_index.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="exibe o resultado em JSON",
    )
    source_index.set_defaults(func=command_source_index)

    source_list = source_subparsers.add_parser(
        "list",
        help="lista as fontes de um workspace",
    )
    source_list.add_argument(
        "--workspace",
        type=int,
        required=True,
        dest="workspace_id",
        help="ID do workspace",
    )
    source_list.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="exibe o resultado em JSON",
    )
    source_list.set_defaults(func=command_source_list)

    source_show = source_subparsers.add_parser(
        "show",
        help="exibe uma fonte e seu snapshot",
    )
    source_show.add_argument("source_id", type=int, help="ID da fonte")
    source_show.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="exibe o resultado em JSON",
    )
    source_show.set_defaults(func=command_source_show)


# Registra os subcomandos de PDF.
def _add_pdf_parser(subparsers: argparse._SubParsersAction) -> None:
    pdf = subparsers.add_parser(
        "pdf",
        help="inspeciona, sugere e preenche formulários PDF",
    )
    pdf_subparsers = pdf.add_subparsers(
        dest="pdf_command",
        required=True,
    )

    pdf_fields = pdf_subparsers.add_parser(
        "fields",
        help="lista os campos AcroForm de uma fonte PDF",
    )
    pdf_fields.add_argument(
        "--source",
        type=int,
        required=True,
        dest="source_id",
        help="ID da fonte PDF",
    )
    pdf_fields.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="exibe o resultado em JSON",
    )
    pdf_fields.set_defaults(func=command_pdf_fields)

    pdf_suggest = pdf_subparsers.add_parser(
        "suggest",
        help="gera sugestões por campo com perfil, vetores e IA",
    )
    pdf_suggest.add_argument(
        "--source",
        type=int,
        required=True,
        dest="source_id",
        help="ID da fonte PDF",
    )
    pdf_suggest.add_argument(
        "--instructions",
        default="",
        help="instruções adicionais para as sugestões",
    )
    pdf_suggest.add_argument(
        "--refresh",
        action="store_true",
        help="regenera sugestões preservando edições manuais",
    )
    pdf_suggest.add_argument(
        "--new",
        action="store_true",
        help="cria uma nova sessão em vez de reutilizar a aberta",
    )
    pdf_suggest.add_argument(
        "--output",
        default=None,
        help="grava as sugestões em um arquivo JSON",
    )
    pdf_suggest.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="exibe o resultado em JSON",
    )
    pdf_suggest.set_defaults(func=command_pdf_suggest)

    pdf_show = pdf_subparsers.add_parser(
        "show",
        help="exibe uma sessão de preenchimento",
    )
    pdf_show.add_argument("session_id", type=int, help="ID da sessão")
    pdf_show.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="exibe o resultado em JSON",
    )
    pdf_show.set_defaults(func=command_pdf_show)

    pdf_set = pdf_subparsers.add_parser(
        "set",
        help="edita manualmente um campo da sessão",
    )
    pdf_set.add_argument("session_id", type=int, help="ID da sessão")
    pdf_set.add_argument("field_name", help="nome do campo PDF")
    pdf_set.add_argument("value", help="novo valor do campo")
    pdf_set.add_argument(
        "--approve",
        action="store_true",
        help="aprova o campo após a edição",
    )
    pdf_set.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="exibe o resultado em JSON",
    )
    pdf_set.set_defaults(func=command_pdf_set)

    pdf_approve = pdf_subparsers.add_parser(
        "approve",
        help="aprova um ou todos os campos",
    )
    pdf_approve.add_argument("session_id", type=int, help="ID da sessão")
    pdf_approve.add_argument(
        "--field",
        default=None,
        dest="field_name",
        help="nome do campo a aprovar",
    )
    pdf_approve.add_argument(
        "--all",
        action="store_true",
        help="aprova todos os campos com valor",
    )
    pdf_approve.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="exibe o resultado em JSON",
    )
    pdf_approve.set_defaults(func=command_pdf_approve)

    pdf_fill = pdf_subparsers.add_parser(
        "fill",
        help="grava uma cópia preenchida do PDF",
    )
    pdf_fill.add_argument("session_id", type=int, help="ID da sessão")
    pdf_fill.add_argument(
        "--output",
        required=True,
        help="caminho do novo PDF preenchido",
    )
    pdf_fill.add_argument(
        "--values",
        default=None,
        help="arquivo JSON com valores para aplicar antes de preencher",
    )
    pdf_fill.add_argument(
        "--flatten",
        action="store_true",
        help="achata as aparências dos campos no PDF",
    )
    pdf_fill.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="exibe o resultado em JSON",
    )
    pdf_fill.set_defaults(func=command_pdf_fill)


# Registra os subcomandos de chat.
def _add_chat_parser(subparsers: argparse._SubParsersAction) -> None:
    chat = subparsers.add_parser(
        "chat",
        help="conversa com o agente e usa fontes quando disponíveis",
    )
    chat_subparsers = chat.add_subparsers(
        dest="chat_command",
        required=True,
    )

    chat_ask = chat_subparsers.add_parser(
        "ask",
        help="faz uma pergunta única à área de trabalho",
    )
    chat_ask.add_argument("question", help="pergunta em linguagem natural")
    chat_ask.add_argument(
        "--workspace",
        type=int,
        required=True,
        dest="workspace_id",
        help="ID do workspace",
    )
    chat_ask.add_argument(
        "--top-k",
        type=int,
        default=None,
        dest="top_k",
        help="quantidade de trechos recuperados",
    )
    chat_ask.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="exibe a resposta em JSON",
    )
    chat_ask.set_defaults(func=command_chat_ask)

    chat_repl = chat_subparsers.add_parser(
        "repl",
        help="inicia uma conversa interativa",
    )
    chat_repl.add_argument(
        "--workspace",
        type=int,
        required=True,
        dest="workspace_id",
        help="ID do workspace",
    )
    chat_repl.add_argument(
        "--top-k",
        type=int,
        default=None,
        dest="top_k",
        help="quantidade de trechos recuperados",
    )
    chat_repl.set_defaults(func=command_chat_repl)

    chat_status = chat_subparsers.add_parser(
        "status",
        help="exibe a situação do índice",
    )
    chat_status.add_argument(
        "--workspace",
        type=int,
        required=True,
        dest="workspace_id",
        help="ID do workspace",
    )
    chat_status.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="exibe o resultado em JSON",
    )
    chat_status.set_defaults(func=command_chat_status)


# Monta o parser principal da CLI.
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agente_editais_ia",
        description="Agente local para editais e propostas de solução.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="habilita logs detalhados",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser(
        "doctor",
        help="verifica configuração, banco, Ollama e Playwright",
    )
    doctor.set_defaults(func=command_doctor)

    _add_help_parser(subparsers)
    _add_tui_parser(subparsers)
    _add_profile_parser(subparsers)
    _add_inspect_parser(subparsers)
    _add_workspace_parser(subparsers)
    _add_source_parser(subparsers)
    _add_pdf_parser(subparsers)
    _add_chat_parser(subparsers)
    _add_proposal_parser(subparsers)

    return parser


# Executa o comando escolhido pelo usuário.
def main(argv: list[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)

    if not raw_args or raw_args == ["--debug"]:
        configure_logging(get_settings(), debug=bool(raw_args))
        try:
            return _open_tui()
        except KeyboardInterrupt:
            print("\nOperação cancelada pelo usuário.", file=sys.stderr)
            return 130

    parser = build_parser()
    args = parser.parse_args(raw_args)

    configure_logging(get_settings(), debug=args.debug)

    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("\nOperação cancelada pelo usuário.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
