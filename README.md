# TattoWeb

A portfolio, studio and shop website for a tattoo artist who also produces paintings,
illustrations and digital artwork.

The site is built to read as **an artist's world**, not a commercial booking funnel. Its
visual identity — *INK AS DATA* — treats black ink and paper craft through a digital
interface layer: halftone dither, monospaced technical metadata, 1px hairlines, and an
electric cobalt accent used so sparingly it earns attention.

> **Independent project.** TattoWeb shares no code, database or configuration with any
> other project on this machine.

---

## Status: complete through Phase 12

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py seed_placeholders
uv run python manage.py seed_sample_art
uv run python manage.py runserver 8000          # the site + CMS
uv run uvicorn api_service.main:app --port 8001 # the JSON API
uv run pytest                                    # 240+ tests
```

---

## Architecture

```
Browser ──HTML──► Django 5.2 (pages, admin/CMS, forms) ─┐
        └─JSON──► FastAPI (public API :8001) ───────────┤
                                                        ▼
                                            PostgreSQL 15 (one schema,
                                             owned by Django migrations)

services/  framework-free business rules, imported by BOTH stacks
```

**Django owns:** the schema, the CMS at `/admin/`, all HTML, all forms, auth.
**FastAPI owns:** the public read API, availability, search, image derivatives. It never
renders HTML and never owns a table.
**`services/`** holds the real rules (availability, images, SEO) so the two stacks call the
*same* code and cannot drift.

### Why the API package is called `api_service/`

A local package named `fastapi/` shadows the installed `fastapi` library — `from fastapi
import FastAPI` resolves to the local directory and the import fails. Renamed to
`api_service/` so the name is unambiguous.

---

## Stack

| Layer | Choice |
|---|---|
| Language | Python 3.13 via `uv` + `.venv` |
| Web | Django 5.2 LTS, Django REST Framework |
| API | FastAPI, Pydantic v2, SQLAlchemy 2 |
| Serving | Gunicorn (WSGI, Django) + Uvicorn (ASGI, FastAPI) |
| Database | PostgreSQL 15 |
| Frontend | Django Templates, hand-written CSS, vanilla ES6 modules |
| Images | Pillow (derivatives + halftone plates), `cwebp` |
| Tests | pytest, pytest-django, httpx |

**Deliberately absent:** React, a Node build pipeline, Redis, Celery, Alembic, GraphQL,
Docker-for-local-dev. Each is justified in `docs/architecture.md` §2 — the short version
is that nothing at this scale needs them, and adding them would be cargo-culting.

---

## Local setup

### Prerequisites

```bash
psql --version                 # PostgreSQL 15 (Homebrew)
uv --version                   # uv
brew services list | grep postgresql@15
```

### 1. Database

```bash
/opt/homebrew/opt/postgresql@15/bin/createdb tattoweb
/opt/homebrew/opt/postgresql@15/bin/psql -d tattoweb -c "CREATE EXTENSION IF NOT EXISTS btree_gist;"
```

`btree_gist` is **required**: it enables the `EXCLUDE USING gist` constraint that makes
double-booking structurally impossible rather than merely checked in Python.

### 2. Environment

```bash
cd ~/hermesPRO/TattoWeb
uv sync
cp .env.example .env      # then edit
```

### 3. Run

```bash
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py seed_placeholders   # site settings, styles, availability
uv run python manage.py seed_sample_art     # 12 gothic engraving demo pieces

uv run python manage.py runserver 8000
uv run uvicorn api_service.main:app --reload --port 8001
```

| URL | What |
|---|---|
| `http://127.0.0.1:8000/` | The site |
| `http://127.0.0.1:8000/admin/` | The CMS |
| `http://127.0.0.1:8000/design-system/` | Visual system reference (staff, debug only) |
| `http://127.0.0.1:8000/healthz/` | Liveness probe |
| `http://127.0.0.1:8001/api/v1/docs` | API documentation |
| `http://127.0.0.1:8000/sitemap.xml` | Sitemap index |

---

## Environment variables

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | required in prod |
| `DEBUG` | `True` in dev only |
| `ALLOWED_HOSTS` | comma-separated |
| `DATABASE_URL` | `postgres://temurbek@127.0.0.1:5432/tattoweb` |
| `CORS_ALLOWED_ORIGINS` | allow-list, never `*` with credentials |
| `FASTAPI_BASE_URL` | `http://127.0.0.1:8001` |
| `MEDIA_ROOT` / `STATIC_ROOT` | paths |
| `IMAGE_MAX_UPLOAD_MB` | upload cap, enforced server-side |
| `SITE_TIMEZONE` | availability and appointment timezone |
| `STATIC_VERSION` | dev cache-busting stamp |
| `DESIGN_SYSTEM_ENABLED` | force the internal reference page on/off |
| `EMAIL_*` | optional; booking notifications log instead when unset |

---

## The image system

Every upload generates, synchronously in 0.2–1.5s:

- five WebP derivatives (400/800/1200/1600/2400) — never upscaled
- a **halftone/dither plate** (the signature treatment)
- a 24px LQIP placeholder

The dither is generated at **upload** time, so the dither→full transition costs zero
runtime CPU. `DitherImage` stacks both layers; hover resolves the halftone into the
artwork over 420ms.

**The dither threshold is per image, not global.** Measured: high-key paper-ground
engraving needs a low value to keep thin lines; dark-ground work needs a high one or it
crushes to a solid block. Tune it per asset in the admin.

Uploads are validated four ways — extension allow-list, size cap, magic bytes, and Pillow
`verify()`. SVG is rejected outright as an XSS vector.

---

## The dither algorithm (and why it is what it is)

Ordered (Bayer 8×8) dithering, but with two non-obvious requirements discovered by
measuring the output rather than assuming:

1. **Pre-blur before dithering.** A per-pixel 1-bit decision destroys anything thinner
   than one dot cell. Fine-line engraving *is* that thin, so deciding at full resolution
   shatters every line into specks. A Gaussian low-pass first makes each dot carry the
   average tone of its neighbourhood — which is how a printed screen reproduces a drawing.

2. **Render at reduced resolution, then upscale with NEAREST.** At full resolution each
   cell is 1px and the pattern is finer than the eye integrates, so it reads as noise.
   Rendering at 1/2–1/4 and upscaling makes each cell a visible block — the dot becomes an
   object the eye can read.

`tests/test_images.py` measures the structural signature (intra-cell agreement must exceed
inter-cell agreement) so the noise regression cannot return silently.

---

## Tests

```bash
uv run pytest                                   # full suite
uv run pytest --cov=apps --cov=services --cov=api_service
uv run python manage.py check
uv run python manage.py check --deploy
```

The four that matter most:

| Test | Proves |
|---|---|
| `test_booking_rules.py` | the no-double-booking rule, including under simulated concurrency |
| `test_schema_contract.py` | SQLAlchemy mirrors match the live Postgres schema |
| `test_model_integrity.py` | every `save()` override calls `super().save()` |
| `test_images.py` | the dither is a structured screen, not noise |

Each of those guards a bug that was real and silent.

---

## Project structure

```
config/        Django settings (base/dev/test/prod), urls, wsgi, asgi
apps/          core artists tattoos artworks gallery booking clients shop contact accounts
api_service/   FastAPI service layer (public JSON)
services/      framework-free rules shared by both stacks
templates/     base/ pages/ components/ admin/
static/        css/ js/ img/ fonts/
docs/          the documentation set
reference/     the analysed reference images
tests/
media/         uploads (gitignored)
```

---

## Documentation set

| File | Contents |
|---|---|
| `docs/visual-analysis.md` | Per-image analysis of the five design references, measured palettes |
| `docs/art-direction.md` | Gothic engraving art references and the treatment vocabulary |
| `docs/design-system.md` | Colour, type, space, form, image treatment, motion |
| `docs/architecture.md` | Stack, decisions, the Django↔FastAPI boundary |
| `docs/erd.md` | Complete schema: fields, relations, constraints, indexes, delete behaviour |
| `docs/django-apps.md` | Why each app exists, dependency graph |
| `docs/url-map.md` | Every route in both stacks |
| `docs/fastapi.md` | Service-layer responsibility, schemas, contract test, security |
| `docs/components.md` | Component contracts and their source references |
| `docs/pages.md` | Page-by-page hierarchy and CMS sources |
| `docs/implementation-plan.md` | The 12 phases and their verification gates |
| `docs/deployment.md` | Vercel Services architecture, routing, env vars, media limits |

---

## Deployment notes

Deployed as **two Vercel Services in one project** (Django + FastAPI, one domain).
See `docs/deployment.md` for the architecture, the routing table, the required
environment variables, and the media-storage limitation. The local two-process
description below is still how development runs.

- Two processes behind one reverse proxy: `/api/v1/*` → FastAPI, everything else → Django.
  One public origin, which is why CORS is a dev-only concern.
- **Settings are selected by `DJANGO_SETTINGS_MODULE`, not by `DEBUG` in `.env`.**
  The production servers default to `config.settings.prod` (`config/wsgi.py`,
  `config/asgi.py`), which forces `DEBUG=False`, requires an explicit `ALLOWED_HOSTS`,
  and **refuses to start** if `DJANGO_SECRET_KEY` or `ALLOWED_HOSTS` are missing — so a
  deployment cannot silently inherit the development configuration. `manage.py` defaults
  to `config.settings.dev` because it is a developer tool; pass the module explicitly for
  production management commands.
- Secure cookies, HSTS, `X_FRAME_OPTIONS=DENY` and `SECURE_SSL_REDIRECT` are applied by
  `config.settings.prod`.
- Static and media served by the proxy, never by Django.
  `collectstatic` produces 176 content-hashed files with a manifest.
- Backup Postgres and the media directory together — the images are irreplaceable.
- No secrets in the repository.

### Production checklist

```bash
export DJANGO_SETTINGS_MODULE=config.settings.prod

uv run python manage.py check --deploy           # must report 0 issues
uv run python manage.py collectstatic --noinput
uv run python manage.py migrate
uv run pytest
```

`check --deploy` is only meaningful under `config.settings.prod`. Run under `dev` it
always warns (W004/W008/W012/W016/W018), because development is not hardened — that is
correct behaviour, not a defect.

### Starting the production servers

```bash
# Django (HTML, CMS, forms)
uv run gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3

# FastAPI (public JSON API)
uv run uvicorn api_service.main:app --host 127.0.0.1 --port 8001 --workers 2
```

Both import a module whose settings default is `config.settings.prod`, so neither will
boot with `DEBUG=True` by accident.

---

## Design principles (for anyone editing this codebase)

1. **Cobalt is rationed.** Never more than ~5% of a viewport. It is an accent for borders,
   active states and one CTA — never body text (2.76:1 contrast, deliberately).
2. **Zero radius, hairline borders, no shadows.** Depth comes from value, not elevation.
3. **Off-white, never `#FFFFFF`. Near-black, never `#000000`.**
4. **The dither-to-full transition is the signature.** Pre-generated, never runtime.
5. **Business logic never lives in templates, views or serializers.** It lives in `services/`.
6. **Content is CMS-driven.** Nothing important is hard-coded.
7. **Works without JavaScript.** Every form, filter and page functions with JS disabled.
8. **Demonstration content is labelled.** `is_placeholder=True` renders a visible notice,
   so generated sample artwork can never be mistaken for the artist's real work.
9. **No technology without a justification.**
