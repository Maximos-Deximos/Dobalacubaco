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


# Verifica se o serviço Ollama responde e se o modelo está instalado.
def _check_ollama(host: str, model: str) -> tuple[bool, str]:
    url = host.rstrip("/") + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            payload = json.load(response)
    except Exception as exc:
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
    except Exception as exc:
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
