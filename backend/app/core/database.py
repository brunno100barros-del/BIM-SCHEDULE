"""Persistência SQLAlchemy.

O engine é criado por :func:`init_database` durante a inicialização do serviço
(e não na importação do módulo), para que a pasta de dados seja resolvida antes.
Os processos de tarefas em segundo plano criam seus próprios engines com
:func:`create_engine_for_url`.
"""
from __future__ import annotations

from typing import Iterator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, future=True)

_engine: Optional[Engine] = None

SQLITE_BUSY_TIMEOUT_MS = 10_000


def _configure_sqlite(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection, _record):  # pragma: no cover - executado pelo driver
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        # WAL permite leitura pela API enquanto um processo de tarefa grava progresso.
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
        cursor.close()


def create_engine_for_url(url: str, *, worker: bool = False) -> Engine:
    is_sqlite = url.startswith("sqlite")
    kwargs: dict = {"future": True}
    if is_sqlite:
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": SQLITE_BUSY_TIMEOUT_MS / 1000}
    if worker:
        kwargs["poolclass"] = NullPool
    engine = create_engine(url, **kwargs)
    if is_sqlite:
        _configure_sqlite(engine)
    return engine


def init_database(url: str) -> Engine:
    """Cria (ou recria) o engine principal e vincula ``SessionLocal`` a ele."""
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = create_engine_for_url(url)
    SessionLocal.configure(bind=_engine)
    return _engine


def dispose_database() -> None:
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("Banco de dados não inicializado. Chame init_database() na inicialização.")
    return _engine


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
