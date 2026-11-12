# Carrega e centraliza as configurações da aplicação.

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"


# Converte variáveis de ambiente textuais em booleanos.
def _env_bool(values: Mapping[str, str], key: str, default: bool) -> bool:
    raw = values.get(key, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on", "sim"}


# Converte variáveis de ambiente textuais em inteiros.
def _env_int(values: Mapping[str, str], key: str, default: int) -> int:
    raw = values.get(key, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{key} deve ser um número inteiro.") from exc


# Converte listas separadas por vírgula em tuplas normalizadas.
def _env_list(values: Mapping[str, str], key: str) -> tuple[str, ...]:
    raw = values.get(key, "")
    return tuple(item.strip().lower() for item in raw.split(",") if item.strip())


# Resolve caminhos relativos a partir da raiz do projeto.
def _env_path(values: Mapping[str, str], key: str, base: Path) -> Path | None:
    raw = values.get(key, "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


# Configuração imutável carregada do ambiente.
@dataclass(frozen=True, slots=True)
class Settings:
    project_root: Path
    data_dir: Path
    database_url: str
    ollama_host: str
    ollama_model: str
    ollama_timeout: int
    allowed_domains: tuple[str, ...]
    denied_domains: tuple[str, ...]
    allow_private_networks: bool
    allow_http: bool
    headless: bool
    max_actions: int
    execution_timeout: int
    max_source_bytes: int
    max_pdf_bytes: int
    fetch_timeout: int
    max_redirects: int
    max_linked_pdfs: int
    fetch_user_agent: str
    sensitive_field_action: str
    log_level: str
    log_file: Path | None

    # Monta a configuração a partir do ambiente informado.
    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        values = os.environ if env is None else env

        sensitive_action = values.get("SENSITIVE_FIELD_ACTION", "confirm").strip().lower()
        if sensitive_action not in {"confirm", "skip"}:
            raise ValueError("SENSITIVE_FIELD_ACTION deve ser 'confirm' ou 'skip'.")

        data_dir = _env_path(values, "DATA_DIR", PROJECT_ROOT) or DEFAULT_DATA_DIR
        database_url = values.get("DATABASE_URL", "").strip()
        if not database_url:
            database_url = f"sqlite:///{data_dir / 'agent.db'}"

        return cls(
            project_root=PROJECT_ROOT,
            data_dir=data_dir,
            database_url=database_url,
            ollama_host=values.get("OLLAMA_HOST", "http://127.0.0.1:11434").strip(),
            ollama_model=values.get("OLLAMA_MODEL", "qwen3.5:4b").strip(),
            ollama_timeout=_env_int(values, "OLLAMA_TIMEOUT", 120),
            allowed_domains=_env_list(values, "ALLOWED_DOMAINS"),
            denied_domains=_env_list(values, "DENIED_DOMAINS"),
            allow_private_networks=_env_bool(values, "ALLOW_PRIVATE_NETWORKS", False),
            allow_http=_env_bool(values, "ALLOW_HTTP", False),
            headless=_env_bool(values, "HEADLESS", False),
            max_actions=_env_int(values, "MAX_ACTIONS", 200),
            execution_timeout=_env_int(values, "EXECUTION_TIMEOUT", 180),
            max_source_bytes=_env_int(values, "MAX_SOURCE_BYTES", 20_971_520),
            max_pdf_bytes=_env_int(values, "MAX_PDF_BYTES", 52_428_800),
            fetch_timeout=_env_int(values, "FETCH_TIMEOUT", 30),
            max_redirects=_env_int(values, "MAX_REDIRECTS", 5),
            max_linked_pdfs=_env_int(values, "MAX_LINKED_PDFS", 10),
            fetch_user_agent=values.get(
                "FETCH_USER_AGENT",
                "agente-editais-ia/0.1",
            ).strip(),
            sensitive_field_action=sensitive_action,
            log_level=values.get("LOG_LEVEL", "INFO").strip().upper(),
            log_file=_env_path(values, "LOG_FILE", PROJECT_ROOT),
        )


# Carrega o arquivo .env uma única vez e devolve a configuração.
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    return Settings.from_env()
