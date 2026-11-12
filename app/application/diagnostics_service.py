# Diagnóstico compartilhado entre a CLI e a interface de terminal.

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from pathlib import Path

from app.ai.ollama_client import OllamaClient, OllamaError
from app.config import Settings, get_settings
from app.memory.database import init_db


# Resultado individual de uma verificação de ambiente.
@dataclass(frozen=True, slots=True)
class DiagnosticCheck:
    name: str
    ok: bool
    detail: str


# Compara nomes de modelos tratando a tag implícita ":latest" como equivalente.
def model_installed(model: str, installed: set[str]) -> bool:
    normalized = model.removesuffix(":latest")
    return any(name.removesuffix(":latest") == normalized for name in installed)


# Verifica se os modelos de chat e embedding estão instalados.
def check_ollama(
    host: str,
    timeout: int,
    model: str,
    embed_model: str,
) -> tuple[bool, str, bool, str]:
    try:
        names = set(OllamaClient(host=host, timeout=timeout).list_models())
    except OllamaError as exc:
        detail = f"não foi possível consultar o Ollama em {host}: {exc}"
        return False, detail, False, detail

    chat_ok = model_installed(model, names)
    chat_detail = (
        f"modelo '{model}' disponível"
        if chat_ok
        else f"modelo '{model}' ausente; execute: ollama pull {model}"
    )

    if not embed_model:
        embed_ok = True
        embed_detail = "modelo de embedding não configurado; busca lexical ativa"
    else:
        embed_ok = model_installed(embed_model, names)
        embed_detail = (
            f"modelo '{embed_model}' disponível"
            if embed_ok
            else f"modelo '{embed_model}' ausente; execute: ollama pull {embed_model}"
        )

    return chat_ok, chat_detail, embed_ok, embed_detail


# Verifica se o pacote e os navegadores do Playwright estão instalados.
def check_playwright() -> tuple[bool, str]:
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


# Executa as verificações de instalação e configuração.
def run_diagnostics(settings: Settings | None = None) -> list[DiagnosticCheck]:
    settings = settings or get_settings()
    checks: list[DiagnosticCheck] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append(DiagnosticCheck(name=name, ok=ok, detail=detail))

    add("configuração", True, f"modelo={settings.ollama_model}")

    try:
        init_db(settings.database_url)
        add("banco de dados", True, settings.database_url)
    except Exception as exc:  # noqa: BLE001
        add("banco de dados", False, str(exc))

    data_dir_ok = settings.data_dir.exists() and os.access(settings.data_dir, os.W_OK)
    add("diretório de dados", data_dir_ok, str(settings.data_dir))

    ollama_ok, ollama_detail, embed_ok, embed_detail = check_ollama(
        settings.ollama_host,
        settings.ollama_timeout,
        settings.ollama_model,
        settings.ollama_embed_model,
    )
    add("ollama", ollama_ok, ollama_detail)
    add("embedding", embed_ok, embed_detail)

    playwright_ok, playwright_detail = check_playwright()
    add("playwright", playwright_ok, playwright_detail)

    return checks


# Fachada usada pela interface de terminal.
class DiagnosticsService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def run(self) -> list[DiagnosticCheck]:
        return run_diagnostics(self.settings)
