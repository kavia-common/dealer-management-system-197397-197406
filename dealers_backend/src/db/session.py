from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.config import get_settings

_settings = get_settings()

# Using synchronous SQLAlchemy engine; FastAPI will run it in threadpool for request handlers.
_engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
)

_SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=_engine,
)


# PUBLIC_INTERFACE
def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a SQLAlchemy session.

    Yields:
        Session: database session, closed after request.
    """
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


# PUBLIC_INTERFACE
def get_engine():
    """Return the SQLAlchemy engine (useful for health checks/migrations)."""
    return _engine
