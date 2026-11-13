# Configuração de logging com remoção de dados sensíveis.

from __future__ import annotations

import logging
import re
import sys
from logging.handlers import RotatingFileHandler

from app.config import Settings

SENSITIVE_PATTERN = re.compile(
    r"(?i)\b(password|senha|passwd|token|secret|api[_-]?key|cvv|ssn|cpf|credit[_-]?card)\b"
    r"(\s*[:=]\s*)([^\s,;]+)"
)

_configured = False


# Substitui valores sensíveis por *** antes de emitir o log.
class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        record.msg = SENSITIVE_PATTERN.sub(r"\1\2***", message)
        record.args = ()
        return True


# Usa o stderr atual em cada emissão para sobreviver a redirecionamentos.
class DynamicStreamHandler(logging.StreamHandler):
    @property
    def stream(self):
        return sys.stderr

    @stream.setter
    def stream(self, _value) -> None:
        pass


# Configura o logger raiz uma única vez.
def configure_logging(settings: Settings, debug: bool = False) -> None:
    global _configured

    level_name = "DEBUG" if debug else settings.log_level
    level = getattr(logging, level_name, logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)

    if _configured:
        return

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )

    console_handler = DynamicStreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(RedactionFilter())
    root.addHandler(console_handler)

    if settings.log_file:
        settings.log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            settings.log_file,
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(RedactionFilter())
        root.addHandler(file_handler)

    _configured = True
