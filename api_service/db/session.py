"""
SQLAlchemy engine and session.

FastAPI reads the schema Django owns. It never runs DDL and never creates tables — that
would give the project two competing sources of truth for its schema, which is the
failure mode this architecture exists to avoid (docs/architecture.md §3).
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from api_service.settings import settings

# pool_pre_ping: a long-lived connection can be dropped by Postgres or a proxy; without
# this the first request after an idle period fails with a confusing operational error.
engine = create_engine(
    settings.sqlalchemy_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    future=True,
)


@event.listens_for(engine, "connect")
def _set_timezone(dbapi_connection, connection_record):
    """
    Force UTC on every connection.

    The availability engine compares datetimes against Django-written rows; if one side
    interprets a naive timestamp as local and the other as UTC, slots silently shift by
    hours. Pinning the session timezone removes that class of bug entirely.
    """
    with dbapi_connection.cursor() as cursor:
        cursor.execute("SET TIME ZONE 'UTC'")


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session]:
    """FastAPI dependency yielding a session, closed on request teardown."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_connection() -> bool:
    """Return True when the database answers. Never raises -- the probe must not 500."""
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
