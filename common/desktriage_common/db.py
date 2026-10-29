"""Database session for the API and the worker.

The schema in db/init is applied by the PostgreSQL container when the data
volume is first created. Later schema changes need a new script or a migration.
This module opens sessions against that database and does not create tables.

A completed unit of work is committed. A failure rolls the session back, so a
crashed request leaves the ticket unchanged.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from desktriage_common.config import get_settings

_engine: Engine | None = None


def get_engine() -> Engine:
    """Return the process-wide engine for DATABASE_URL."""
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    return _engine


@contextmanager
def get_session() -> Iterator[Session]:
    """Open a session, commit on success, and roll back on failure."""
    with Session(get_engine()) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def check_session() -> None:
    """Open a session and confirm the database answers."""
    with get_session() as session:
        session.execute(text("SELECT 1"))
