# Carrega e centraliza as configurações da aplicação.

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

from app.ai.provider import (
    DEFAULT_CHAT_MODELS,
    DEFAULT_EMBED_MODELS,
    SUPPORTED_CHAT_PROVIDERS,
    SUPPORTED_EMBED_PROVIDERS,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"

# Variáveis aceitas como chave de API de cada provedor de chat.
CHAT_API_KEY_ENV: dict[str, tuple[str, ...]] = {
    "openai": ("AI_API_KEY", "OPENAI_API_KEY"),
    "openrouter": ("AI_API_KEY", "OPENROUTER_API_KEY"),
    "groq": ("AI_API_KEY", "GROQ_API_KEY"),
    "deepseek": ("AI_API_KEY", "DEEPSEEK_API_KEY"),
    "anthropic": ("AI_API_KEY", "ANTHROPIC_API_KEY"),
    "gemini": ("AI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"),
}

# Variáveis aceitas como chave de API de cada provedor de embedding.
EMBED_API_KEY_ENV: dict[str, tuple[str, ...]] = {
    "openai": ("AI_EMBED_API_KEY", "OPENAI_API_KEY", "AI_API_KEY"),
    "gemini": (
        "AI_EMBED_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "AI_API_KEY",
    ),
}


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


# Converte variáveis de ambiente textuais em números decimais.
def _env_float(values: Mapping[str, str], key: str, default: float) -> float:
    raw = values.get(key, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{key} deve ser um número decimal.") from exc


# Converte listas separadas por vírgula em tuplas normalizadas.
def _env_list(values: Mapping[str, str], key: str) -> tuple[str, ...]:
    raw = values.get(key, "")
    return tuple(item.strip().lower() for item in raw.split(",") if item.strip())


# Devolve o primeiro valor não vazio entre as variáveis informadas.
def _env_first(
    values: Mapping[str, str],
    keys: tuple[str, ...],
    default: str = "",
) -> str:
    for key in keys:
        raw = values.get(key, "").strip()
        if raw:
            return raw
    return default


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
    ollama_embed_model: str
    ollama_timeout: int
    ai_provider: str
    ai_model: str
    ai_api_key: str
    ai_base_url: str
    ai_timeout: int
    ai_max_tokens: int
    ai_embed_provider: str
    ai_embed_model: str
    ai_embed_api_key: str
    ai_embed_base_url: str
    rag_chunk_chars: int
    rag_chunk_overlap: int
    rag_top_k: int
    rag_max_context_chars: int
    rag_embed_batch: int
    rag_history_turns: int
    rag_temperature: float
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

        # Provedor de chat: Ollama local por padrão, externo por chave de API.
        ai_provider = values.get("AI_PROVIDER", "ollama").strip().lower() or "ollama"
        if ai_provider not in SUPPORTED_CHAT_PROVIDERS:
            supported = ", ".join(sorted(SUPPORTED_CHAT_PROVIDERS))
            raise ValueError(
                f"AI_PROVIDER inválido: '{ai_provider}'. Use um de: {supported}."
            )

        # Provedor de embedding: local por padrão para preservar privacidade.
        ai_embed_provider = (
            values.get("AI_EMBED_PROVIDER", "ollama").strip().lower() or "ollama"
        )
        if ai_embed_provider not in SUPPORTED_EMBED_PROVIDERS:
            supported = ", ".join(sorted(SUPPORTED_EMBED_PROVIDERS))
            raise ValueError(
                "AI_EMBED_PROVIDER inválido: "
                f"'{ai_embed_provider}'. Use um de: {supported}."
            )

        legacy_model = values.get("OLLAMA_MODEL", "").strip()
        legacy_embed_model = values.get("OLLAMA_EMBED_MODEL", "").strip()
        legacy_timeout = _env_int(values, "OLLAMA_TIMEOUT", 120)

        if ai_provider == "ollama":
            ai_model = (
                values.get("AI_MODEL", "").strip()
                or legacy_model
                or DEFAULT_CHAT_MODELS["ollama"]
            )
        else:
            ai_model = (
                values.get("AI_MODEL", "").strip()
                or DEFAULT_CHAT_MODELS[ai_provider]
            )

        if ai_embed_provider == "none":
            ai_embed_model = ""
        elif ai_embed_provider == "ollama":
            ai_embed_model = (
                values.get("AI_EMBED_MODEL", "").strip()
                or legacy_embed_model
                or DEFAULT_EMBED_MODELS["ollama"]
            )
        else:
            ai_embed_model = (
                values.get("AI_EMBED_MODEL", "").strip()
                or DEFAULT_EMBED_MODELS[ai_embed_provider]
            )

        ai_api_key = _env_first(
            values,
            CHAT_API_KEY_ENV.get(ai_provider, ("AI_API_KEY",)),
        )
        ai_embed_api_key = _env_first(
            values,
            EMBED_API_KEY_ENV.get(ai_embed_provider, ("AI_EMBED_API_KEY", "AI_API_KEY")),
        )

        # Valida antecipadamente a configuração de provedores externos.
        if ai_provider != "ollama" and not ai_api_key:
            raise ValueError(
                f"O provedor '{ai_provider}' exige uma chave de API. "
                "Defina AI_API_KEY (ou a variável específica) no .env."
            )
        if ai_embed_provider in {"openai", "gemini"} and not ai_embed_api_key:
            raise ValueError(
                f"O provedor de embedding '{ai_embed_provider}' exige uma chave "
                "de API. Defina AI_EMBED_API_KEY no .env."
            )

        ai_timeout = _env_int(values, "AI_TIMEOUT", legacy_timeout)
        ai_max_tokens = _env_int(values, "AI_MAX_TOKENS", 2048)
        if ai_timeout < 1:
            raise ValueError("AI_TIMEOUT deve ser pelo menos 1.")
        if ai_max_tokens < 1:
            raise ValueError("AI_MAX_TOKENS deve ser pelo menos 1.")

        rag_chunk_chars = _env_int(values, "RAG_CHUNK_CHARS", 1800)
        rag_chunk_overlap = _env_int(values, "RAG_CHUNK_OVERLAP", 250)
        rag_top_k = _env_int(values, "RAG_TOP_K", 6)
        rag_max_context_chars = _env_int(values, "RAG_MAX_CONTEXT_CHARS", 12_000)
        rag_embed_batch = _env_int(values, "RAG_EMBED_BATCH", 16)
        rag_history_turns = _env_int(values, "RAG_HISTORY_TURNS", 6)
        rag_temperature = _env_float(values, "RAG_TEMPERATURE", 0.1)

        if rag_chunk_chars < 100:
            raise ValueError("RAG_CHUNK_CHARS deve ser pelo menos 100.")
        if rag_chunk_overlap < 0 or rag_chunk_overlap >= rag_chunk_chars:
            raise ValueError(
                "RAG_CHUNK_OVERLAP deve ser maior ou igual a zero e menor que "
                "RAG_CHUNK_CHARS."
            )
        if rag_top_k < 1:
            raise ValueError("RAG_TOP_K deve ser pelo menos 1.")
        if rag_max_context_chars < 100:
            raise ValueError("RAG_MAX_CONTEXT_CHARS deve ser pelo menos 100.")
        if rag_embed_batch < 1:
            raise ValueError("RAG_EMBED_BATCH deve ser pelo menos 1.")
        if rag_history_turns < 0:
            raise ValueError("RAG_HISTORY_TURNS não pode ser negativo.")
        if not 0 <= rag_temperature <= 2:
            raise ValueError("RAG_TEMPERATURE deve estar entre 0 e 2.")

        return cls(
            project_root=PROJECT_ROOT,
            data_dir=data_dir,
            database_url=database_url,
            ollama_host=values.get("OLLAMA_HOST", "http://127.0.0.1:11434").strip(),
            # Campos mantidos para compatibilidade com configurações antigas.
            ollama_model=legacy_model or DEFAULT_CHAT_MODELS["ollama"],
            ollama_embed_model=legacy_embed_model or DEFAULT_EMBED_MODELS["ollama"],
            ollama_timeout=legacy_timeout,
            ai_provider=ai_provider,
            ai_model=ai_model,
            ai_api_key=ai_api_key,
            ai_base_url=values.get("AI_BASE_URL", "").strip(),
            ai_timeout=ai_timeout,
            ai_max_tokens=ai_max_tokens,
            ai_embed_provider=ai_embed_provider,
            ai_embed_model=ai_embed_model,
            ai_embed_api_key=ai_embed_api_key,
            ai_embed_base_url=values.get("AI_EMBED_BASE_URL", "").strip(),
            rag_chunk_chars=rag_chunk_chars,
            rag_chunk_overlap=rag_chunk_overlap,
            rag_top_k=rag_top_k,
            rag_max_context_chars=rag_max_context_chars,
            rag_embed_batch=rag_embed_batch,
            rag_history_turns=rag_history_turns,
            rag_temperature=rag_temperature,
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
