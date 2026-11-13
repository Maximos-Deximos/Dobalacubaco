# Diagnóstico compartilhado entre a CLI e a interface de terminal.

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from pathlib import Path

from app.ai.factory import build_chat_provider, build_embed_provider
from app.ai.ollama_client import OllamaClient, OllamaError
from app.ai.provider import AiError, AiProvider
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


# Verifica se os modelos de chat e embedding estão instalados no Ollama.
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


# Consulta a lista de modelos e confirma se o modelo configurado existe.
def check_provider_models(
    provider: AiProvider,
    model: str,
    *,
    label: str,
) -> tuple[bool, str]:
    try:
        names = set(provider.list_models())
    except AiError as exc:
        return False, f"{label}: falha ao consultar modelos: {exc}"

    if not model:
        return False, f"{label}: nenhum modelo configurado"

    if model_installed(model, names):
        return True, f"{label}: modelo '{model}' disponível"

    if provider.name == "ollama":
        return False, f"{label}: modelo '{model}' ausente; execute: ollama pull {model}"
    return False, (
        f"{label}: modelo '{model}' não aparece na lista do provedor; "
        "verifique AI_MODEL/AI_EMBED_MODEL"
    )


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


# Monta uma verificação de chat para o provedor configurado.
def check_chat_provider(settings: Settings) -> tuple[bool, str]:
    label = f"chat ({settings.ai_provider})"
    try:
        provider = build_chat_provider(settings)
    except ValueError as exc:
        return False, f"{label}: {exc}"
    return check_provider_models(provider, settings.ai_model, label=label)


# Monta uma verificação de embedding para o provedor configurado.
def check_embed_provider(settings: Settings) -> tuple[bool, str]:
    if settings.ai_embed_provider == "none":
        return True, "embeddings desativados; busca lexical ativa"

    label = f"embedding ({settings.ai_embed_provider})"
    try:
        provider = build_embed_provider(settings)
    except ValueError as exc:
        return False, f"{label}: {exc}"
    if provider is None:
        return True, "embeddings desativados; busca lexical ativa"
    return check_provider_models(provider, settings.ai_embed_model, label=label)


# Executa as verificações de instalação e configuração.
def run_diagnostics(settings: Settings | None = None) -> list[DiagnosticCheck]:
    settings = settings or get_settings()
    checks: list[DiagnosticCheck] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append(DiagnosticCheck(name=name, ok=ok, detail=detail))

    add(
        "configuração",
        True,
        (
            f"chat={settings.ai_provider}/{settings.ai_model}; "
            f"embedding={settings.ai_embed_provider}/"
            f"{settings.ai_embed_model or '(desativado)'}"
        ),
    )

    try:
        init_db(settings.database_url)
        add("banco de dados", True, settings.database_url)
    except Exception as exc:  # noqa: BLE001
        add("banco de dados", False, str(exc))

    data_dir_ok = settings.data_dir.exists() and os.access(settings.data_dir, os.W_OK)
    add("diretório de dados", data_dir_ok, str(settings.data_dir))

    chat_ok, chat_detail = check_chat_provider(settings)
    add("provedor de chat", chat_ok, chat_detail)

    embed_ok, embed_detail = check_embed_provider(settings)
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
