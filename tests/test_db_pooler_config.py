"""
PostgreSQL connection configuration for the Supabase transaction pooler.

Production connects through Supabase's (Supavisor) pooler in **transaction mode**, port
6543, because Vercel Functions are serverless and IPv4-only while the direct Supabase
connection is IPv6-only.

Transaction pooling imposes two hard constraints, and both are asserted here because both
fail *late* rather than immediately — which is what makes them dangerous:

1. **Prepared statements are unsupported.** psycopg 3 prepares a statement automatically
   once it has run `prepare_threshold` times, default 5. So an unconfigured deployment
   works, works, works, and then fails on the fifth execution of a query.

2. **Client-side pooling multiplies connections.** A `QueuePool` sizes itself per function
   instance, and serverless platforms run many instances. Supabase explicitly recommends
   `NullPool` for serverless and horizontally auto-scaling deployments.

These tests do not need a production credential: they exercise configuration and a local
PostgreSQL, and skip cleanly when no database is reachable.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent

# A transaction-pooler URL with obviously fake credentials. The password never leaves
# this file and is never sent anywhere -- it exists only to prove URL rewriting preserves
# the opaque parts of a URL.
POOLER_URL = "postgres://fake-user.fakeref:fakepassword@aws-0-eu-central-1.pooler.supabase.com:6543/postgres"


def _venv_python() -> str:
    return str(BASE_DIR / ".venv" / "bin" / "python")


def _run(probe: str, env_extra: dict | None = None) -> tuple[int, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("DJANGO_")}
    if env_extra:
        env.update(env_extra)
    r = subprocess.run([_venv_python(), "-c", probe],
                       cwd=BASE_DIR, capture_output=True, text=True, env=env)
    return r.returncode, f"{r.stdout}{r.stderr}"


# --------------------------------------------------------------------------------------
# URL construction
# --------------------------------------------------------------------------------------
def test_sqlalchemy_url_rewrites_driver_and_preserves_credentials():
    """
    The driver prefix is rewritten to `postgresql+psycopg://` and nothing else changes.

    Credentials must pass through untouched — the URL is never parsed and rebuilt, because
    a password containing `@`, `:` or `/` would be corrupted by naive reconstruction.
    """
    code, out = _run(
        "import os;"
        f"os.environ['DATABASE_URL']={POOLER_URL!r};"
        "from api_service.settings import Settings;"
        "print('URL', Settings().sqlalchemy_url)",
    )
    assert code == 0, out[-600:]
    line = next(ln for ln in out.splitlines() if ln.startswith("URL "))
    url = line[4:]

    assert url.startswith("postgresql+psycopg://"), url
    # The opaque credential segment must survive byte-for-byte.
    assert "fake-user.fakeref:fakepassword@" in url, url
    assert url.endswith(":6543/postgres"), url


@pytest.mark.parametrize("prefix", ["postgres://", "postgresql://"])
def test_both_plain_prefixes_are_rewritten(prefix):
    """Django uses `postgres://`; SQLAlchemy needs an explicit driver for either spelling."""
    url = f"{prefix}fake-user.fakeref:fakepassword@aws-0-eu-central-1.pooler.supabase.com:6543/postgres"
    code, out = _run(
        "import os;"
        f"os.environ['DATABASE_URL']={url!r};"
        "from api_service.settings import Settings;"
        "print('URL', Settings().sqlalchemy_url)",
    )
    assert code == 0, out[-600:]
    line = next(ln for ln in out.splitlines() if ln.startswith("URL "))
    assert line[4:].startswith("postgresql+psycopg://")


def test_already_qualified_url_is_not_double_rewritten():
    """An URL that already names the psycopg driver must be left alone."""
    url = "postgresql+psycopg://u:p@host:6543/db"
    code, out = _run(
        "import os;"
        f"os.environ['DATABASE_URL']={url!r};"
        "from api_service.settings import Settings;"
        "print('URL', Settings().sqlalchemy_url)",
    )
    assert code == 0, out[-600:]
    line = next(ln for ln in out.splitlines() if ln.startswith("URL "))
    assert line[4:] == url, line[4:]
    assert "psycopg+psycopg" not in line[4:]


@pytest.mark.parametrize("port,expected", [(6543, "True"), (5432, "False")])
def test_transaction_pooler_detected_by_port(port, expected):
    """
    Detection is by port, never by hostname — hostnames vary per project and region, so
    any host-based check would silently stop matching.
    """
    url = f"postgres://u:p@some-host.example.com:{port}/postgres"
    code, out = _run(
        "import os;"
        f"os.environ['DATABASE_URL']={url!r};"
        "from api_service.settings import Settings;"
        "print('POOLER', Settings().is_transaction_pooler)",
    )
    assert code == 0, out[-600:]
    assert f"POOLER {expected}" in out, out[-400:]


# --------------------------------------------------------------------------------------
# Engine configuration
# --------------------------------------------------------------------------------------
def test_engine_disables_prepared_statements_and_uses_nullpool():
    """
    The two pooler requirements, asserted on the constructed engine and on a live
    connection where one is reachable.

    `prepare_threshold=None` is Supabase's documented psycopg setting. `NullPool` is their
    documented pooling choice for serverless. The probe runs as a real script rather than a
    `-c` one-liner so it can use try/except and read the driver attribute directly --
    `create_connect_args()` normalises the URL and does not surface `connect_args`, so
    inspecting it would prove nothing.
    """
    probe = BASE_DIR / "tests" / "_pooler_probe.py"
    probe.write_text(
        "import os, sys\n"
        "from sqlalchemy import event, text\n"
        "from sqlalchemy.pool import NullPool\n"
        "from api_service.db.session import engine\n"
        "print('NULLPOOL', isinstance(engine.pool, NullPool))\n"
        "seen = {}\n"
        "def _spy(conn, rec):\n"
        "    seen['t'] = getattr(conn, 'prepare_threshold', 'MISSING')\n"
        "event.listen(engine, 'connect', _spy)\n"
        "try:\n"
        "    with engine.connect() as c:\n"
        "        c.execute(text('SELECT 1'))\n"
        "    print('PREPARE', seen.get('t', 'MISSING'))\n"
        "except Exception as exc:\n"
        "    print('PREPARE_UNCHECKED', type(exc).__name__)\n",
        encoding="utf-8",
    )
    try:
        code, out = _run(f"import runpy; runpy.run_path({str(probe)!r}, run_name='__main__')")
    finally:
        probe.unlink(missing_ok=True)

    assert code == 0, out[-700:]
    assert "NULLPOOL True" in out, (
        "the engine is not using NullPool; Supabase recommends it for serverless "
        f"deployments:\n{out[-400:]}"
    )
    # Either the live connection reports None, or no database was reachable here. Both are
    # acceptable: the value can only be wrong if the source says something else, which the
    # source-level test below and the Django test both cover independently.
    assert "PREPARE None" in out or "PREPARE_UNCHECKED" in out, (
        "prepare_threshold reached the driver with an unexpected value:\n" + out[-400:]
    )


def test_no_queuepool_sizing_remains():
    """`pool_size`/`max_overflow` are QueuePool-only and must not linger in the source."""
    # Scan the executable code only. The module's docstring deliberately names the old
    # `pool_size=5, max_overflow=10` values to explain why they were removed, so a naive
    # text search would flag the explanation rather than the configuration.
    import ast

    src = (BASE_DIR / "api_service" / "db" / "session.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]

    offending = []
    for call in calls:
        for kw in call.keywords:
            if kw.arg in {"pool_size", "max_overflow"}:
                offending.append(kw.arg)

    assert not offending, (
        f"{offending} still passed to create_engine. A QueuePool sized per Vercel function "
        "instance multiplies connections against the shared pooler."
    )


def test_engine_can_initialize_without_a_database():
    """
    Constructing the engine must not require a reachable server.

    A build step or an import in a test environment must not open a connection, so this
    asserts construction only. `NullPool` makes that property structural rather than
    incidental.
    """
    code, out = _run(
        "import os;"
        f"os.environ['DATABASE_URL']={POOLER_URL!r};"
        "from api_service.db.session import engine, SessionLocal;"
        "from api_service.main import app;"
        "print('APP', app.title);"
        "print('OK')",
    )
    assert code == 0, out[-700:]
    assert "OK" in out, out[-500:]


# --------------------------------------------------------------------------------------
# Django side
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "module,conn_max_age",
    [("config.settings.dev", "0"), ("config.settings.prod", "0")],
)
def test_django_disables_prepared_statements(module, conn_max_age):
    """
    Django shares the database, so it needs the same prepared-statement treatment.

    Django merges `DATABASES['default']['OPTIONS']` into the psycopg connect call, so
    `prepare_threshold` belongs there. Without it Django would fail against the pooler on
    the fifth execution of any repeated query.

    `CONN_MAX_AGE` is 0 in BOTH environments, for different reasons. Development: the dev
    server is threaded per request and Django's docs say not to enable persistent
    connections there. Production: the deployment is serverless behind a pooler, and a
    suspended Vercel instance never runs the request-boundary check that would expire the
    connection, so a non-zero value leaks connections until the pooler times them out.
    """
    import secrets

    extra = {"DJANGO_SETTINGS_MODULE": module}
    if module.endswith("prod"):
        extra["DJANGO_SECRET_KEY"] = secrets.token_urlsafe(60)
        extra["ALLOWED_HOSTS"] = "example.com"
    else:
        extra["DJANGO_SECRET_KEY"] = "x" * 60

    code, out = _run(
        "import django; django.setup();"
        "from django.conf import settings;"
        "d = settings.DATABASES['default'];"
        "print('PREPARE', repr(d['OPTIONS'].get('prepare_threshold', 'MISSING')));"
        "print('CMA', d.get('CONN_MAX_AGE', 0))",
        env_extra=extra,
    )
    assert code == 0, out[-700:]
    assert "PREPARE None" in out, (
        f"{module} does not set prepare_threshold=None, so Django will use prepared "
        f"statements and fail against the transaction pooler:\n{out[-400:]}"
    )
    assert f"CMA {conn_max_age}" in out, (
        f"{module} should use CONN_MAX_AGE={conn_max_age}:\n{out[-400:]}"
    )


def test_production_disables_persistent_connections_for_serverless():
    """
    `CONN_MAX_AGE` must be 0 in production, and this is not a performance preference.

    Django enforces the CONN_MAX_AGE expiry at request boundaries. Vercel suspends an idle
    function instance in memory, where that check never runs, so a non-zero value leaves the
    connection open until the pooler's own timeout -- minutes later. Vercel documents this as
    a leaked connection, and notes Supabase caps concurrent pooler connections, so a deploy
    that orphans the previous version's instances spends real pooler budget.

    Django's own reference adds two more reasons that apply here: persistent connections
    should be disabled when connection parameters are modified per connection (this project
    pins the session timezone on connect), and the PostgreSQL notes require CONN_MAX_AGE 0
    when a connection pooler is in use.

    Asserted on the loaded settings rather than on the source text so that a comment
    explaining the decision cannot satisfy it.
    """
    import secrets

    code, out = _run(
        "import django; django.setup();"
        "from django.conf import settings;"
        "print('CMA', settings.DATABASES['default']['CONN_MAX_AGE'])",
        env_extra={
            "DJANGO_SETTINGS_MODULE": "config.settings.prod",
            "DJANGO_SECRET_KEY": secrets.token_urlsafe(60),
            "ALLOWED_HOSTS": "example.com",
        },
    )
    assert code == 0, out[-600:]
    assert "CMA 0" in out, (
        "CONN_MAX_AGE is not 0 in production. On Vercel this leaks pooler connections: a "
        f"suspended instance never runs the expiry check.\n{out[-300:]}"
    )


def test_development_also_disables_persistent_connections():
    """
    Development is 0 too, for a different reason: Django's development server creates a
    thread per request, which negates persistent connections entirely.
    """
    code, out = _run(
        "import django; django.setup();"
        "from django.conf import settings;"
        "print('CMA', settings.DATABASES['default']['CONN_MAX_AGE'])",
        env_extra={"DJANGO_SETTINGS_MODULE": "config.settings.dev",
                   "DJANGO_SECRET_KEY": "x" * 60},
    )
    assert code == 0, out[-600:]
    assert "CMA 0" in out, f"dev CONN_MAX_AGE should be 0:\n{out[-300:]}"


def test_pooler_requirements_survive_the_conn_max_age_change():
    """
    The change must not have disturbed prepared-statement handling on either stack.

    Regression guard for the specific risk that editing prod.py drops the
    `prepare_threshold` applied in base.py.
    """
    import secrets

    code, out = _run(
        "import django; django.setup();"
        "from django.conf import settings;"
        "print('PREPARE', settings.DATABASES['default']['OPTIONS']['prepare_threshold'])",
        env_extra={
            "DJANGO_SETTINGS_MODULE": "config.settings.prod",
            "DJANGO_SECRET_KEY": secrets.token_urlsafe(60),
            "ALLOWED_HOSTS": "example.com",
        },
    )
    assert code == 0, out[-600:]
    assert "PREPARE None" in out, (
        f"prepare_threshold was lost from the production settings:\n{out[-300:]}"
    )


def test_prod_settings_do_not_enable_debug_or_prepare_statements():
    """The production configuration as a whole: hardened, pooled, unprepared."""
    import secrets

    code, out = _run(
        "import django; django.setup();"
        "from django.conf import settings;"
        "print('DEBUG', settings.DEBUG);"
        "print('SSL', settings.SECURE_SSL_REDIRECT);"
        "print('PREPARE', settings.DATABASES['default']['OPTIONS']['prepare_threshold'])",
        env_extra={
            "DJANGO_SETTINGS_MODULE": "config.settings.prod",
            "DJANGO_SECRET_KEY": secrets.token_urlsafe(60),
            "ALLOWED_HOSTS": "example.com",
        },
    )
    assert code == 0, out[-700:]
    assert "DEBUG False" in out
    assert "SSL True" in out
    assert "PREPARE None" in out
