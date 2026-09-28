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

`config.settings.build` exists because the build must satisfy two constraints that no other
settings module can:

- It must not require a secret. `prod.py` correctly raises `ImproperlyConfigured` without
  `DJANGO_SECRET_KEY` — right for a server, fatal for a build.
- It must not import a dev-only package. `dev.py` adds `debug_toolbar`, and
  `django-debug-toolbar` is a dev-group dependency that must not be installed in a
  production build.

`config.settings.build` inherits `base`, keeps `DEBUG` off, and is used only to collect
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
