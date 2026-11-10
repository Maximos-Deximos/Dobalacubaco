# Testes de criação e uso básico do banco SQLite.

import pytest
from sqlalchemy import inspect, select

from app.memory.database import init_db, reset_engine, session_scope
from app.memory.models import UserProfileModel


# Cria uma URL isolada de banco para cada teste.
@pytest.fixture
def database_url(tmp_path) -> str:
    return f"sqlite:///{tmp_path / 'test.db'}"


# Descarta a engine global após cada teste.
@pytest.fixture(autouse=True)
def cleanup_engine() -> None:
    yield
    reset_engine()


# Confere se as três tabelas iniciais são criadas.
def test_init_db_creates_tables(database_url: str) -> None:
    engine = init_db(database_url)
    tables = set(inspect(engine).get_table_names())

    assert {"user_profiles", "executions", "execution_fields"} <= tables


# Confere commit automático e leitura de um perfil.
def test_session_scope_persists_profile(database_url: str) -> None:
    init_db(database_url)

    with session_scope(database_url) as session:
        session.add(UserProfileModel(name="default", full_name="Pessoa Teste"))

    with session_scope(database_url) as session:
        profile = session.scalar(
            select(UserProfileModel).where(UserProfileModel.name == "default")
        )

    assert profile is not None
    assert profile.full_name == "Pessoa Teste"
