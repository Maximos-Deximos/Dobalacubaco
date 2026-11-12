# Ponto de entrada da CLI do agente.

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import urllib.request
from pathlib import Path

from app.config import get_settings
from app.logging_config import configure_logging
from app.memory.database import init_db
from app.ui.browser_cli import command_inspect
from app.ui.cli import (
    command_profile_init,
    command_profile_set,
    command_profile_show,
)
from app.ui.source_cli import (
    command_source_add,
    command_source_add_file,
    command_source_list,
    command_source_show,
)
from app.ui.workspace_cli import (
    command_workspace_list,
    command_workspace_new,
    command_workspace_show,
)


# Verifica se o serviço Ollama responde e se o modelo está instalado.
def _check_ollama(host: str, model: str) -> tuple[bool, str]:
    url = host.rstrip("/") + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            payload = json.load(response)
    except Exception as exc:  # noqa: BLE001
        return False, f"não foi possível conectar em {host}: {exc}"

    names = {
        item.get("name", "")
        for item in payload.get("models", [])
        if isinstance(item, dict)
    }
    if not any(name == model for name in names):
        return False, f"modelo '{model}' ausente; execute: ollama pull {model}"

    return True, f"modelo '{model}' disponível"


# Verifica se o pacote e os navegadores do Playwright estão instalados.
def _check_playwright() -> tuple[bool, str]:
    if importlib.util.find_spec("playwright") is None:
        return False, "pacote playwright não instalado"

    browser_root = Path(
        os.environ.get(
            "PLAYWRIGHT_BROWSERS_PATH",
            str(Path.home() / ".cache" / "ms-playwright"),
        )
    )
    if not browser_root.exists() or not any(browser_root.iterdir()):
        return False, "navegadores ausentes; execute: playwright install chromium"

    return True, f"navegadores em {browser_root}"


# Executa verificações básicas de instalação e configuração.
def command_doctor(_args: argparse.Namespace) -> int:
    settings = get_settings()
    checks: list[tuple[str, bool, str]] = []

    def add_check(name: str, ok: bool, detail: str) -> None:
        checks.append((name, ok, detail))

    add_check("configuração", True, f"modelo={settings.ollama_model}")

    try:
        init_db()
        add_check("banco de dados", True, settings.database_url)
    except Exception as exc:  # noqa: BLE001
        add_check("banco de dados", False, str(exc))

    data_dir_ok = settings.data_dir.exists() and os.access(settings.data_dir, os.W_OK)
    add_check("diretório de dados", data_dir_ok, str(settings.data_dir))

    ollama_ok, ollama_detail = _check_ollama(settings.ollama_host, settings.ollama_model)
    add_check("ollama", ollama_ok, ollama_detail)

    playwright_ok, playwright_detail = _check_playwright()
    add_check("playwright", playwright_ok, playwright_detail)

    failed = False
    for name, ok, detail in checks:
        status = "OK" if ok else "FALHA"
        if not ok:
            failed = True
        print(f"[{status:5}] {name}: {detail}")

    return 1 if failed else 0


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


# Monta o parser principal da CLI.
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agente_editais_ia",
        description="Agente local para preenchimento de editais.",
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

    _add_profile_parser(subparsers)
    _add_inspect_parser(subparsers)
    _add_workspace_parser(subparsers)
    _add_source_parser(subparsers)

    return parser


# Executa o comando escolhido pelo usuário.
def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    configure_logging(get_settings(), debug=args.debug)

    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("\nOperação cancelada pelo usuário.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
