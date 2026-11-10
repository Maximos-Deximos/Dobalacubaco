# Fixtures compartilhadas para testes com banco isolado.

import pytest

from app.config import get_settings
from app.memory.database import reset_engine


# Cria um banco SQLite temporário e limpa o cache de configuração.
@pytest.fixture
def isolated_database(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    reset_engine()

    yield database_url

    reset_engine()
    get_settings.cache_clear()
