"""
app/db/state/db.py — Database engine and session factory (Phase 1).

Provides:
  - get_engine()  : create or return a cached SQLAlchemy engine.
  - get_session() : context manager that yields a Session and commits/rolls back.
  - create_tables(): create all ORM-mapped tables (idempotent).

Uses SQLite for testing (no Postgres required in CI) via the DATABASE_URL env var.
In production use: DATABASE_URL=postgresql://vitian:vitian_pw@localhost:5432/vitian_chatbot
"""

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.state.models import Base

logger = logging.getLogger(__name__)

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def get_engine(database_url: str | None = None) -> Engine:
    """
    Return the shared SQLAlchemy engine.

    Lazily created on first call.  Pass database_url to override the settings
    singleton (useful in tests with a temp SQLite DB).
    """
    global _engine, _SessionLocal
    if _engine is not None and database_url is None:
        return _engine

    if database_url is None:
        from app.config import settings
        database_url = settings.database_url

    connect_args = {}
    if database_url.startswith("sqlite"):
        # Enable WAL mode and foreign keys for SQLite (used in tests)
        connect_args = {"check_same_thread": False}

    engine = create_engine(
        database_url,
        connect_args=connect_args,
        echo=False,
        pool_pre_ping=True,
    )

    # Enable foreign keys for SQLite connections
    if database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(conn, _record):
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA journal_mode=WAL")

    if database_url is None:
        _engine = engine
        _SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    return engine


def get_session_factory(database_url: str | None = None) -> sessionmaker:
    """Return the session factory, creating the engine if needed."""
    engine = get_engine(database_url)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@contextmanager
def get_session(database_url: str | None = None) -> Generator[Session, None, None]:
    """
    Context manager that yields a database Session.

    Commits on success, rolls back on any exception.

    Usage::

        with get_session() as db:
            db.add(my_object)
    """
    factory = get_session_factory(database_url)
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_tables(database_url: str | None = None) -> None:
    """
    Create all ORM-mapped tables if they do not already exist (idempotent).

    Safe to call multiple times.
    """
    engine = get_engine(database_url)
    Base.metadata.create_all(engine)
    logger.info("Database tables created/verified", extra={"database_url": str(engine.url)})
