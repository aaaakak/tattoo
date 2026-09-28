# Deployment — Vercel Services

TattoWeb is **two applications in one Vercel project**, not one. It is deployed with
[Vercel Services](https://vercel.com/docs/services), which builds multiple frameworks in a
single project and routes them through one public routing table on one domain.

## Architecture

```
                      ┌──────────────────────────────────────────┐
  Public request ───► │  Vercel top-level routing table          │
                      │  (vercel.json → rewrites, in order)      │
                      └───────────────┬──────────────────────────┘
                                      │
                 /api/v1/(.*) ────────┴──────── /(.*)
                        │                            │
                        ▼                            ▼
              ┌──────────────────┐         ┌───────────────────────┐
              │ service: "api"   │         │ service: "web"        │
              │ FastAPI          │         │ Django 5.2            │
              │ api_service.main │         │ config.wsgi           │
              │ :app             │         │ :application          │
              └────────┬─────────┘         └──────────┬────────────┘
                       │                              │
                       └──────────┬───────────────────┘
                                  ▼
                      PostgreSQL 15 (one schema,
                      owned by Django migrations)
```

Both services share the repository root because they share code: `api_service/` imports the
Django ORM through `django.setup()`, and both import the framework-free `services/` layer.
They are isolated by **entrypoint**, not by directory.

## Routing

Top-level rewrites are evaluated in order — first match wins — so the specific API rule
precedes the catch-all. A service receives the **original request path**, so no in-service
rewrites are needed: FastAPI's routers are already mounted at `/api/v1`, and Django's URL
tree already owns everything else.

| Request | Service | Route that handles it |
|---|---|---|
| `/`, all pages | `web` | `apps.core.urls` and friends |
| `/admin/` | `web` | Django admin / custom CMS site |
| `/healthz/` | `web` | `core_views.healthz` (503 when the DB is down) |
| `/sitemap.xml`, `/sitemap-<section>.xml` | `web` | `django.contrib.sitemaps` |
| `/robots.txt` | `web` | `core_views.robots` |
| `/static/*` | `web` | collected, served from the Vercel CDN |
| `/api/v1/*` | `api` | FastAPI routers (content, site, booking, search) |
| `/api/v1/docs`, `/api/v1/openapi.json` | `api` | FastAPI's OpenAPI surface |

**Routing into a service is final.** Vercel does not fall back to another top-level rewrite
once a service matches. That is safe here because `web` genuinely owns every path the `api`
service does not claim.

## Why the FastAPI-only entrypoint was not used

The original build error suggested:

```toml
[tool.vercel]
entrypoint = "api_service.main:app"
```

That is a **single-service** escape hatch. Accepting it would have deployed FastAPI alone
and silently dropped Django — no website, no `/admin/`, no CMS, no sitemap, no forms. The
error appeared *because* Vercel was asked to find one entrypoint in a repository that
deliberately contains two. `vercel.json` names both explicitly instead.

There is deliberately **no `[tool.vercel] entrypoint`** in `pyproject.toml`: that key is a
single top-level value and cannot describe two services. Per-service entrypoints live in
`vercel.json`.

## Build

`web` runs, inside its service:

```
python manage.py collectstatic --noinput --settings=config.settings.build
```

### Vercel runs collectstatic twice, and that is expected

The Django framework preset performs its **own** automatic `collectstatic` after the
service's `buildCommand`. Its invocation is bare:

```
.vercel/python/services/web/.venv/bin/python manage.py collectstatic --noinput
```

No `--settings`, so it resolves `DJANGO_SETTINGS_MODULE` through `manage.py`, which defaults
to `config.settings.dev`.

This caused two separate problems, both fixed:

**1. The automatic run crashed.** `dev.py` used to install `debug_toolbar`
unconditionally, but `django-debug-toolbar` is a dev-group dependency and is absent from
Vercel's production install:

```
ModuleNotFoundError: No module named 'debug_toolbar'
```

`dev.py` now attaches the toolbar only when the package is actually importable
(`importlib.util.find_spec`, wrapped in `try/except` because `find_spec` propagates an
`ImportError` when an import hook raises one). Development is unchanged for anyone with the
dev group installed; the module is simply no longer unimportable without it. Adding
`django-debug-toolbar` to production dependencies would have been the wrong fix — a
development tool does not belong in a production install.

**2. The build produced no staticfiles manifest.** This was latent and would have shipped
a broken site on the first *successful* build. Production serves with
`ManifestStaticFilesStorage`, so `{% static %}` resolves filenames through
`staticfiles.json`. A build using plain `StaticFilesStorage` produces no such manifest
(Django only writes it for manifest storage, and only `prod` and `build` use it), so every
asset URL fails at runtime:

```
ValueError: Missing staticfiles manifest entry for 'css/base.css'
```

A healthy-looking deployment serving unstyled pages is worse than a failed build.
`config.settings.build` now uses `ManifestStaticFilesStorage` so the manifest the
production settings expect is actually generated.

The two runs are harmless in either order: `collectstatic` never deletes, it only copies, so
the hashed files and `staticfiles.json` written by the build step survive the automatic run.
Verified by running build-then-dev collection and confirming the manifest persists.

### Why config.settings.build exists

It must satisfy two constraints that no other settings module can:

- It must not require a secret. `prod.py` correctly raises `ImproperlyConfigured` without
  `DJANGO_SECRET_KEY` — right for a server, fatal for a build.
- It must not depend on a dev-only package, so `dev` is not a safe build target.

It inherits `base`, keeps `DEBUG` off, requires no secret, and is used only to collect
static files. It never serves anything: the entrypoint Vercel loads resolves to
`config.settings.prod`, which still hard-fails on a missing secret. Verify with:

```bash
DJANGO_SETTINGS_MODULE=config.settings.prod python -c "import django; django.setup()"
# → ImproperlyConfigured, as it must be
```

`api` has no build step; it is pure Python.

## Environment variables (set in the Vercel project, not committed)

Both services receive all project variables, so one value each covers both.

| Variable | Example | Notes |
|---|---|---|
| `DJANGO_SECRET_KEY` | 60+ random chars | **Required.** `prod.py` refuses to boot without it. The FastAPI service needs it too, because it initializes Django to share the ORM. |
| `ALLOWED_HOSTS` | `tattoo.example.com,.vercel.app` | **Required.** Comma-separated. Include the deployment host and the real domain. |
| `DATABASE_URL` | `postgres://…` | **Required.** Postgres. Django owns the schema; FastAPI never issues DDL. |
| `CSRF_TRUSTED_ORIGINS` | `https://tattoo.example.com` | Needed or admin/form POSTs fail CSRF checks behind the proxy. |
| `FASTAPI_BASE_URL` | `https://tattoo.example.com` | Set to the public origin; same origin as Django behind Vercel's routing. |
| `CORS_ALLOWED_ORIGINS` | *(empty)* | One origin fronts both stacks, so this may be empty. Never `*` with credentials. |
| `MEDIA_ROOT` | `/tmp/media` | See the media limitation below. |
| `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS` | `True`, `31536000` | Defaults in `prod.py` are already correct. |
| `DESIGN_SYSTEM_ENABLED` | `False` | Keeps the internal reference route absent in production. |
| `EMAIL_*` | — | Optional; booking notifications log to console when unset. |

Never commit a real value. `.env`, `.env.local` and `.vercel/` are gitignored.

### Optional variables must not be defined as empty strings

A hosting platform may create a variable with an **empty value** rather than omitting it.
Vercel did exactly this with `IMAGE_MAX_UPLOAD_MB`, and the first deployment failed with:

```
File config/settings/base.py:
    IMAGE_MAX_UPLOAD_MB = env.int("IMAGE_MAX_UPLOAD_MB", default=12)
ValueError: invalid literal for int() with base 10: ''
```

`django-environ` treats an empty variable as *present*, so the declared default is skipped
and `int("")` is evaluated. Historically that failed in three separate ways:

| Call shape | With an empty value | Consequence |
|---|---|---|
| `env.int(..., default=12)` | raises `ValueError` | **the settings import crashes** |
| `env.bool(..., default=True)` | returns `False` | **silently disables a security setting** |
| `env.list(..., default=[...])` | returns `[]` | silently discards the default |

`config/settings/base.py` now wraps every typed read in `env_int` / `env_bool` / `env_str` /
`env_list`, which treat an empty or whitespace-only value as **"not supplied"** so the
declared default applies. A value that is actually provided still wins, and a genuinely
malformed value (e.g. `IMAGE_MAX_UPLOAD_MB=abc`) still fails loudly rather than being
quietly replaced — empty is ambiguous, garbage is a mistake.

**The correct configuration is to omit optional variables entirely.** If a variable must
exist in the dashboard, leave its value genuinely empty only because the code now tolerates
it; omitting is clearer. Required variables (`DJANGO_SECRET_KEY`, `ALLOWED_HOSTS`,
`DATABASE_URL`) must never be empty — `prod.py` still refuses to boot without them.


## Database connection — Supabase transaction pooler

Production connects through the Supabase (Supavisor) pooler in **transaction mode, port
6543**. Transaction mode is required rather than merely preferred: Vercel Functions are
serverless and **IPv4-only**, and Supabase's direct connection is IPv6-only, so the direct
port is unreachable from Vercel at all.

Transaction pooling imposes two constraints, and both fail *late* — which is what makes
them worth documenting.

### 1. No prepared statements

Supavisor in transaction mode does not support prepared statements. psycopg 3 prepares a
statement automatically once it has executed it `prepare_threshold` times, and that
threshold defaults to **5**. So an unconfigured deployment works, then fails on the fifth
execution of a repeated query — a symptom that looks like anything but its cause.

Supabase's documented psycopg setting is `prepare_threshold=None`. It is applied on both
sides, because both connect:

| Stack | Where | Configuration |
|---|---|---|
| FastAPI / SQLAlchemy | `api_service/db/session.py` | `connect_args={"prepare_threshold": None}` |
| Django | `config/settings/base.py` | `DATABASES["default"]["OPTIONS"]["prepare_threshold"] = None` |

SQLAlchemy's psycopg dialect forwards `connect_args` to `psycopg.Connection.connect()`, and
Django merges `OPTIONS` into the same call — both verified against a live PostgreSQL, where
the connection reports `prepare_threshold = None`.

Statement preparation is not transaction handling. Transactions are untouched:
`autocommit=False`, explicit transactions, no isolation change.

### 2. No client-side pooling

Supabase recommends `NullPool` for serverless and horizontally auto-scaling deployments,
and that is what FastAPI now uses. The previous `pool_size=5, max_overflow=10` was a
`QueuePool` sized **per function instance** — up to 15 simultaneous connections in each
instance, multiplied by however many instances Vercel runs at that moment. Supavisor
already pools server-side, so a second client-side pool adds no benefit and spends a shared
connection budget.

`pool_pre_ping=True` is kept: with `NullPool` a connection may have been closed upstream,
and pre-ping turns that into a reconnect instead of an error.

Django uses `CONN_MAX_AGE = 60` in production and the default `0` in development — 0 so
schema changes are picked up immediately while developing, 60 so production does not redo a
TLS and auth handshake on every request.

`CONN_MAX_AGE` is set in `config/settings/prod.py`, **not** `base.py`. `base.py` cannot
decide it: its `DEBUG` reflects `.env`, and `prod.py` overrides `DEBUG` only after `base`
has run, so an `if not DEBUG` branch there is a silent no-op.

### Verifying the configuration

```bash
python -c "
import os; os.environ['DJANGO_SETTINGS_MODULE']='config.settings.dev'
os.environ.setdefault('DJANGO_SECRET_KEY','x'*50)
import django; django.setup()
from django.db import connection
connection.ensure_connection()
print(connection.connection.prepare_threshold)   # expect: None
"
```

`tests/test_db_pooler_config.py` asserts all of the above, including URL rewriting
(credentials pass through byte-for-byte rather than being parsed and rebuilt), pooler
detection by port, `NullPool` in use, and the absence of any `QueuePool` sizing.

## Media storage — the limitation that must be addressed

**Vercel Functions have a read-only filesystem except `/tmp`, and `/tmp` is per-invocation
and ephemeral.**

TattoWeb writes every upload to `MEDIA_ROOT`, and `ingest_image` generates five WebP
derivatives, a halftone dither plate and an LQIP at upload time, all to disk.

Consequently, **on Vercel:**

- Browsing, the public read API, the CMS UI, forms and auth all work.
- **Uploading an image does not persist.** The derivatives are written, the request ends,
  and the filesystem is discarded. The database row would reference files that no longer
  exist.

The repository is correct as it stands — `media/` is gitignored — so this is a hosting
constraint, not a code defect. Resolving it needs object storage via `django-storages`
(Vercel Blob, or any S3-compatible provider) plus the `STORAGES` setting pointed at it. That
requires a provider decision and credentials, and is **deliberately not done here**.

Until it is, treat image upload on Vercel as unavailable.

## Local development

```bash
vercel dev -L      # runs both services locally, injects bindings, no cloud auth
```

Without the CLI, run the two processes directly as the README describes; that is the normal
development path and needs no Vercel account.

## Verification performed

- `vercel.json` validated against Vercel's published schema (`openapi.vercel.sh/vercel.json`):
  no unknown fields, all required present, every service reachable by a rewrite.
- Build command executed with **no `.env` and no secrets**: 183 static files collected, exit 0.
- Production settings re-checked after adding the build module: still refuse to boot without
  a secret key.
- Full test suite, lint, migration and deploy checks unchanged and passing.

**Not performed:** an actual `vercel build`/deploy. The CLI requires a linked Vercel project
and cannot run without authenticating and pulling project settings, which is out of scope.
Cloud-side validation remains unverified until a deployment is attempted.
