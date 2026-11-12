# Testes da migração inicial do banco.

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.memory.database import reset_engine


# Confere que a migração inicial cria todas as tabelas esperadas.
def test_initial_migration_creates_tables(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "migration.db"
    database_url = f"sqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    reset_engine()

    config = Config(str(Path("alembic.ini")))
    config.set_main_option("script_location", str(Path("migrations")))
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    tables = set(inspect(engine).get_table_names())
    engine.dispose()

    assert {
        "user_profiles",
        "executions",
        "execution_fields",
        "workspaces",
        "sources",
        "source_snapshots",
    } <= tables

    reset_engine()
