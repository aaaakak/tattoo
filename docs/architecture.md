# Architecture — TattoWeb

## 1. Purpose

A premium portfolio and studio site for a single tattoo artist who also produces paintings,
illustrations and digital artwork. It must read as an artist's world, not a booking funnel.
The same system must run a real booking workflow, a lightweight client record, and a shop.

## 2. Stack (confirmed present on this machine)

| Layer | Choice | Verified |
|---|---|---|
| Runtime | Python 3.13 via `uv` + `.venv` | `uv 0.9.28` ✓ |
| Web framework | Django 5.2 LTS + Django REST Framework | to install |
| Database | PostgreSQL 15.19 (`postgresql@15`, Homebrew) | `psql 15.19` ✓ running |
| Service layer | FastAPI + Pydantic v2 + SQLAlchemy 2 | to install |
| Templates | Django Templates + HTML5 + vanilla ES6 | n/a |
| CSS | Hand-authored CSS with custom properties, no framework | n/a |
| Images | Pillow at ingest, `cwebp` for WebP | `cwebp` ✓, PIL ✓ |
| Cache/queue | Locally: Django locmem + DB rows. Redis **not installed** — deliberately deferred | ✓ absent |

### Deliberate omissions (and why)
- **No React / no Node build pipeline.** The site is server-rendered editorial content with
  progressive-enhancement motion. A bundler would add a toolchain, a lockfile ecosystem and a
  second dependency tree for zero product value. Vanilla ES modules ship directly.
- **No Redis.** Nothing in the MVP needs a shared cache or a broker. `LocMemCache` in dev and
  `DatabaseCache` in production cover this workload. Adding Redis now would be cargo-culting.
- **No Celery.** Nothing needs a background worker at launch. Image derivatives are generated
  **synchronously at upload** (bounded, a few hundred ms) and a management command handles
  bulk backfill. If the shop later needs order emails + Stripe webhooks, that is the trigger
  to introduce Celery + Redis — and the code is structured so that swap is local, not global.
- **No Alembic initially.** FastAPI reads Django-owned tables directly via SQLAlchemy
  reflection over the same Postgres schema — one source of truth for the schema, which is
  Django's migrations. Alembic is introduced only if FastAPI ever owns tables of its own.
  This is the decision that most cleanly prevents the classic dual-ORM schema drift.

## 3. The Django ↔ FastAPI responsibility boundary

This is the most important architectural decision in the project, so it is stated precisely.

**Django owns:**
- All schema and all writes to core business data
- All human editing (admin/CMS)
- All HTML rendering and all public page URLs
- Server-side form handling for booking and contact (works with JS disabled)
- Authentication and authorisation

**FastAPI owns:**
- Machine-readable read APIs (`/api/v1/...`) for portfolio, gallery, shop, availability
- Booking submission as a JSON API (used progressively by the booking form)
- Availability computation — a pure function over Django-owned tables
- Search across tattoos/artworks/products
- The image-derivative service: on-demand resize/format negotiation and dither generation
- Future: AI concept generation, image analysis

**Rule:** FastAPI **never** writes to a table Django does not know about, and never
duplicates a Django endpoint that already exists as HTML. Every FastAPI write path
(booking, contact) has a Django-side origin so the site functions without JS.

**Shared access:** FastAPI uses SQLAlchemy 2 with `autocommit=False` sessions against the same
Postgres database. Core tables are declared as SQLAlchemy models under `api_service/db/models.py`,
kept aligned to Django migrations by a **contract test** (`tests/test_schema_contract.py`)
that asserts every SQLAlchemy column exists in the live Postgres schema. That test is what
makes the dual-ORM approach safe rather than fragile.

## 4. Request flow

```
Browser
  │
  ├─ HTML pages ──────────► Django (templates, admin, forms)  ─┐
  │                                                            │
  └─ fetch() JSON ────────► FastAPI (/api/v1) ─────────────────┤
                                                               ▼
                                                     PostgreSQL 15
                                                  (single schema, single
                                                   source of truth =
                                                   Django migrations)

Media: served by web server (nginx/Caddy) in production,
       by Django in dev. FastAPI serves *derived* sizes only.
```

## 5. Project layout

```
~/hermesPRO/TattoWeb/
├── manage.py
├── pyproject.toml
├── .env.example                 # committed
├── .env                         # gitignored
├── .gitignore
├── README.md
├── docs/                        # Phase 1 deliverables
├── reference/                   # the five analysed screenshots
│
├── config/                      # Django project
│   ├── __init__.py
│   ├── settings/
│   │   ├── base.py
│   │   ├── dev.py
│   │   ├── test.py
│   │   └── prod.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
│
├── apps/
│   ├── core/          # SiteSettings, SocialLink, SEO mixins, template tags, services
│   ├── artists/       # ArtistProfile, ArtistStatement, Statistic
│   ├── tattoos/       # TattooStyle, Tattoo, TattooImage
│   ├── artworks/      # ArtworkCategory, Artwork, ArtworkImage
│   ├── gallery/       # GalleryCollection, GalleryImage
│   ├── booking/       # Availability, BlockedDate, Booking, BookingReference, Appointment
│   ├── clients/       # Client
│   ├── shop/          # ProductCategory, Product, ProductImage, Order-ready stubs
│   ├── contact/       # ContactMessage
│   └── accounts/      # artist login, permissions
│
├── api/               # Django REST Framework — serializers, views, routers
│   ├── serializers/
│   ├── views/
│   └── urls.py
│
├── templates/
│   ├── base/          # base.html, head.html, header.html, footer.html, grain.html
│   ├── pages/         # home, tattoos, tattoo_detail, artworks, artwork_detail,
│   │                  # gallery, about, booking, shop, product_detail, contact
│   ├── components/    # dither_image.html, editorial_run.html, meta_list.html, ...
│   └── admin/         # admin overrides
│
├── static/
│   ├── css/           # tokens.css, base.css, layout.css, components.css, pages.css
│   ├── js/            # modules (ES6), no bundler
│   │   ├── main.js
│   │   ├── modules/{reveal,resolve,parallax,lightbox,cursor,transition,forms}.js
│   │   └── vendor/    # nothing, unless justified
│   ├── img/
│   └── fonts/
│
├── media/             # user uploads (gitignored)
│
├── fastapi/           # service layer
│   ├── main.py
│   ├── deps.py
│   ├── settings.py
│   ├── routers/{tattoos,styles,artworks,gallery,bookings,availability,products,search,images}.py
│   ├── schemas/       # Pydantic v2
│   ├── services/      # business logic, no framework imports
│   └── db/{session.py, models.py}
│
├── services/          # shared pure-Python logic importable by BOTH stacks
│   ├── availability.py    # no-double-booking rule, slot computation
│   ├── images.py          # derivative + dither generation
│   └── seo.py
│
└── tests/
    ├── test_models.py
    ├── test_booking_rules.py
    ├── test_api.py
    ├── test_schema_contract.py
    └── test_smoke_pages.py
```

**The `services/` package is the key structural move.** Availability and image logic are
pure Python with no Django or FastAPI imports, so both stacks call the exact same function.
The no-double-booking rule therefore exists once, not twice.

## 6. Configuration & secrets

- All secrets from environment via `django-environ`. `.env.example` committed, `.env` ignored.
- `DJANGO_SECRET_KEY`, `DATABASE_URL`, `DEBUG`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`,
  `FASTAPI_BASE_URL`, `MEDIA_ROOT`, `IMAGE_MAX_UPLOAD_MB`, `RATELIMIT_ENABLE`,
  `DESIGN_SYSTEM_ENABLED`, `STATIC_VERSION`.
- No secret, credential, key or password in source. Enforced by `tests/test_secrets.py`,
  which scans the tree for high-entropy string literals and known key prefixes, asserts
  that `.env` is git-ignored (`git check-ignore`) and untracked, and runs a subprocess that
  boots `config.settings.prod` with no secret key to prove it raises rather than defaulting.
- `prod.py` requires `DEBUG=False`, a non-default secret, explicit `ALLOWED_HOSTS`,
  secure cookies, HSTS, `SECURE_SSL_REDIRECT`, and `X_FRAME_OPTIONS = DENY`.

### Selecting settings

Settings are selected by `DJANGO_SETTINGS_MODULE`, never by the `DEBUG` value in `.env`.
The production entrypoints (`config/wsgi.py`, `config/asgi.py`, `api_service/main.py`)
default to `config.settings.prod`, so a deployment that forgets the variable fails loudly
on a missing secret instead of silently running with `DEBUG=True`. `manage.py` defaults to
`config.settings.dev` because it is a developer tool; production management commands pass
the module explicitly. This is why `manage.py check --deploy` must be run with
`DJANGO_SETTINGS_MODULE=config.settings.prod` -- under `dev` it warns by design.

## 7. Performance strategy

- `select_related` / `prefetch_related` on every list view; `only()` on card querysets.
- DB indexes on every slug, status, `is_featured`, and date field actually filtered on.
- Pagination everywhere; the gallery paginates in chunks of 24.
- Image derivatives pre-generated at upload: `_800`, `_1200`, `_1600`, `_2400` WebP +
  a `_dither` sibling + a 24px LQIP blur placeholder stored per image.
- `<picture>` with `srcset`/`sizes`, `loading="lazy"` and explicit `width`/`height`
  (zero CLS) on everything below the fold; hero image preloaded with `fetchpriority="high"`.
- CSS is a handful of hand-written files with custom properties — no framework, no purge step.
- JS is small ES modules loaded with `type="module"`, deferred, budget **< 30KB** total.
- Long-lived cache headers on hashed static assets.

## 8. Security strategy

CSRF on every form (Django default; FastAPI exposes the token via a Django-served cookie) ·
upload validation by extension AND Pillow verification AND MIME sniff AND a size cap ·
uploads renamed to UUIDs outside the web root's executable paths · no SVG uploads (XSS vector) ·
rate limiting on booking/contact (`django-ratelimit`) and on FastAPI writes (in-process
token bucket) · `ALLOWED_HOSTS` enforced · CORS allow-list, never `*` with credentials ·
DRF default `permission_classes = [IsAuthenticatedOrReadOnly]` with explicit write perms ·
admin protected by `AdminSite` + optional 2FA later · secrets only from env.

## 9. What this architecture deliberately does NOT have

- No microservices. FastAPI runs in-process alongside Django in dev and as a second
  systemd/launchd unit in production. It is a service *layer*, not a distributed system.
- No GraphQL. Nine REST resources do not justify it.
- No Docker requirement for local dev — Postgres is already native here. A Dockerfile is
  provided for deployment only.
- No headless CMS. Django admin *is* the CMS.
- No AI features. `services/` and a `ConceptRequest` model are shaped so AI concept
  generation can be added later, but nothing fake ships now.
