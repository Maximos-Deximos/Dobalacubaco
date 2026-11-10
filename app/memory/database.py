# Criação de engine, sessões e inicialização do banco SQLite.

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_engine: Engine | None = None
_engine_url: str | None = None


# Garante que o diretório do arquivo SQLite exista.
def _prepare_sqlite_directory(database_url: str) -> None:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        return

    database = url.database
    if not database or database == ":memory:":
        return

    Path(database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


# Cria uma engine configurada para o banco informado.
def create_engine_for_url(database_url: str) -> Engine:
    _prepare_sqlite_directory(database_url)

    connect_args = {}
    if make_url(database_url).get_backend_name() == "sqlite":
        connect_args["check_same_thread"] = False

    engine = create_engine(database_url, connect_args=connect_args, future=True)

    if engine.dialect.name == "sqlite":

        # Ativa a verificação de chaves estrangeiras no SQLite.
        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


# Devolve a engine global, recriando-a quando a URL mudar.
def get_engine(database_url: str | None = None) -> Engine:
    global _engine, _engine_url

    url = database_url or get_settings().database_url
    if _engine is None or _engine_url != url:
        if _engine is not None:
            _engine.dispose()
        _engine = create_engine_for_url(url)
        _engine_url = url

    return _engine


# Cria a fábrica de sessões ligada à engine atual.
def get_session_factory(database_url: str | None = None) -> sessionmaker:
    return sessionmaker(
        bind=get_engine(database_url),
        expire_on_commit=False,
        class_=Session,
    )


# Cria todas as tabelas registradas nos modelos ORM.
def init_db(database_url: str | None = None) -> Engine:
    from app.memory.models import Base

    engine = get_engine(database_url)
    Base.metadata.create_all(bind=engine)
    return engine


# Fornece uma sessão com commit automático ou rollback em caso de erro.
@contextmanager
def session_scope(database_url: str | None = None) -> Iterator[Session]:
    session = get_session_factory(database_url)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# Descarta a engine em cache; usado principalmente em testes.
def reset_engine() -> None:
    global _engine, _engine_url

    if _engine is not None:
        _engine.dispose()

    _engine = None
    _engine_url = None
