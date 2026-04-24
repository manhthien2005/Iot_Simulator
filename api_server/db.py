from __future__ import annotations

import os
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _load_repo_env() -> None:
    """Load repo-local .env so direct runtime/test imports can resolve config."""
    env_candidates = [
        Path(__file__).resolve().parents[1] / ".env",
        Path(__file__).resolve().parents[2] / ".env",
    ]
    for env_path in env_candidates:
        if env_path.exists():
            load_dotenv(env_path, override=False)
            break


_load_repo_env()


def _get_database_url() -> str:
    """Read DATABASE_URL from the environment or raise a clear error."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Create Iot_Simulator/.env and add DATABASE_URL=..."
        )
    return url


def _init_db() -> None:
    global _engine, _SessionLocal

    if _engine is None or _SessionLocal is None:
        _engine = create_engine(
            _get_database_url(),
            pool_pre_ping=True,
            pool_size=3,
            max_overflow=5,
            echo=False,
        )
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=_engine,
        )


def get_session_factory() -> sessionmaker[Session]:
    _init_db()
    assert _SessionLocal is not None
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session per request."""
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager for non-request DB access such as runtime heartbeats.

    Rolls back on exception; always closes the session.
    Does not auto-commit — callers that mutate data should call ``db.commit()``
    explicitly (most current usage is SELECT-only).
    """
    db = get_session_factory()()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
