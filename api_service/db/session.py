"""
SQLAlchemy engine and session.

FastAPI reads the schema Django owns. It never runs DDL and never creates tables — that
would give the project two competing sources of truth for its schema, which is the
failure mode this architecture exists to avoid (docs/architecture.md §3).

## Supabase transaction pooler

Production connects through the Supabase (Supavisor) pooler in **transaction mode**
(port 6543), because Vercel Functions are serverless and IPv4-only, and the direct
connection is IPv6-only. Transaction pooling imposes two constraints that the engine
configuration below addresses deliberately:

**1. No prepared statements.** Supavisor in transaction mode does not support them, and
psycopg 3 prepares automatically after 5 executions of the same statement
(`prepare_threshold` defaults to 5). That is invisible until the fifth run of a query,
which makes it a latent production failure rather than an immediate one. Supabase's own
guidance for psycopg is to set `prepare_threshold` to `None`, which is what
`connect_args` does here. The value is forwarded by SQLAlchemy's psycopg dialect straight
to `psycopg.Connection.connect()`.

**2. No client-side pooling.** Supabase recommends `NullPool` for serverless and
horizontally auto-scaling deployments. A `QueuePool` here would size itself *per function
instance*: the previous `pool_size=5, max_overflow=10` allowed 15 simultaneous connections
in a single instance, multiplied by however many instances Vercel runs — the exact pattern
that exhausts a shared pooler. Supavisor already pools server-side, so a second client-side
pool buys nothing and costs connections. `NullPool` opens one connection per checkout and
closes it on release, which is the recommended shape for this deployment.

Transactions are untouched: `NullPool` affects connection lifetime, not transaction
semantics, and `SessionLocal` still runs in explicit transactions with `autocommit=False`.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from api_service.settings import settings

# Supabase transaction mode does not support prepared statements. psycopg 3 starts
# preparing a statement automatically once it has been executed `prepare_threshold` times
# (default 5), so this must be disabled explicitly -- `None` turns automatic preparation
# off entirely. Without it, a query works in development and then fails in production on
# its fifth execution, which is a hard failure to attribute.
connect_args = {"prepare_threshold": None}

engine = create_engine(
    settings.sqlalchemy_url,
    # Supavisor pools server-side; a client-side pool would multiply connections per
    # instance. NullPool is Supabase's documented choice for serverless deployments.
    poolclass=NullPool,
    # Cheap insurance with NullPool: a connection fetched from the pooler may have been
    # closed upstream, and pre-ping turns that into a reconnect rather than an error.
    pool_pre_ping=True,
    connect_args=connect_args,
    future=True,
)


@event.listens_for(engine, "connect")
def _set_timezone(dbapi_connection, connection_record):
    """
    Force UTC on every connection.

    The availability engine compares datetimes against Django-written rows; if one side
    interprets a naive timestamp as local and the other as UTC, slots silently shift by
    hours. Pinning the session timezone removes that class of bug entirely.

    Note on transaction pooling: `SET TIME ZONE` is *session*-scoped, and in transaction
    mode a pooled server connection is handed to another client once the transaction ends,
    so a session-level setting can outlive the client that set it. This is why the setting
    is ALSO applied at connect time through `DATABASE_URL` (libpq startup parameters --
    see api_service/settings.py), which establishes it as part of the server session from
    the outset rather than mutating a borrowed one. The statement below is kept as
    belt-and-braces for deployments that connect directly without pooler options.
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
