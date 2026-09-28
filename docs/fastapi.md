Web# FastAPI Layer — TattoWeb

## 1. Why FastAPI exists here at all

The honest answer first, because the brief says not to introduce technology for its own sake.

Django could serve every one of these endpoints with DRF. So FastAPI must earn its place.
It earns it in exactly four places, and **only** these:

1. **Public read APIs with different caching and traffic characteristics than HTML.**
   The portfolio JSON is hit by the frontend on every page transition and is aggressively
   cacheable. Serving it from a separate async process keeps HTML rendering latency
   independent of API traffic.
2. **Availability computation as a service.** The no-double-booking calculation is a pure
   function over three tables. Exposing it as a JSON endpoint lets the booking form query
   slots live, and lets the same function be unit-tested without Django test scaffolding.
3. **The image-derivative service.** On-demand resizing, format negotiation and **halftone
   dither generation** — this is CPU-bound work best done outside the web-rendering process,
   with its own cache headers and its own concurrency limit.
4. **A typed, documented, versioned contract.** Pydantic v2 schemas + generated OpenAPI give
   a machine-verifiable contract for the frontend and any future client, which DRF
   serializers do not give as cleanly.

If any of those four disappeared, FastAPI would stop being justified. That is the test.

## 2. Explicit non-goals

- **FastAPI does not render HTML.** Not one template.
- **FastAPI is not the admin backend.** The artist never touches it.
- **FastAPI does not own the schema.** Django migrations own it. FastAPI reads it.
- **FastAPI does not duplicate Django write endpoints.** Booking and contact exist as Django
  POST fallbacks *and* FastAPI JSON. The Django path is the source of truth; FastAPI's is the
  progressive-enhancement path. Both call the **same shared service function**, so behaviour
  cannot diverge.
- **No fake AI.** `/api/v1/concept` returns `501 Not Implemented` with a clear message until a
  real generator exists. It is a routed placeholder, not a stub that pretends.

## 3. Structure

```
api_service/
├── main.py                  # app factory, middleware, router mounts, lifespan
├── settings.py              # pydantic-settings, reads the same .env as Django
├── deps.py                  # get_db, pagination, rate-limiter, cache headers
├── db/
│   ├── session.py           # SQLAlchemy 2 engine + sessionmaker (shared engine)
│   └── models.py            # SQLAlchemy models mirroring Django-owned tables
├── schemas/
│   ├── common.py            # Page[T], Envelope, ErrorBody
│   ├── tattoo.py  artwork.py  gallery.py  product.py
│   ├── booking.py  availability.py  site.py
├── routers/
│   ├── tattoos.py  styles.py  artworks.py  gallery.py
│   ├── products.py  search.py  site.py
│   ├── bookings.py  availability.py  contact.py
│   ├── images.py  meta.py  concept.py
└── services/                # thin adapters; real logic lives in /services
    ├── content.py           # queries + shaping
    ├── search.py
    └── images.py
```

**Critical rule:** `api_service/services/*` contains no business rules. It queries and shapes.
The rules (availability, dither algorithm, SEO fallbacks) live in the top-level `services/`
package, framework-free, imported by both stacks.

## 4. Database access

SQLAlchemy 2 ORM, sync sessions (`Session`, not `AsyncSession`).

**Why sync, deliberately:** this workload is small and read-dominated. Async SQLAlchemy with
psycopg adds a second concurrency model and makes the shared-service interop awkward for no
measurable gain at this scale. FastAPI runs sync route handlers in a threadpool, which is
entirely adequate. If profiling later shows the DB is the bottleneck, the swap to
`AsyncSession` is contained to `db/session.py` and the route signatures.

**Table ownership:** Django owns all DDL. `db/models.py` declares read-mirror models with
`__table_args__ = {"extend_existing": True}` semantics avoided — instead a strict 1:1 mirror
verified by a contract test.

```python
# tests/test_schema_contract.py (must pass in CI)
def test_sqlalchemy_mirrors_django_schema():
    """Every column declared in api_service/db/models.py must exist in Postgres,
    and every content table in Postgres must have a mirror."""
    insp = sqlalchemy.inspect(engine)
    live = {t: {c["name"] for c in insp.get_columns(t)} for t in insp.get_table_names()}
    for model in Base.registry.mappers:
        table = model.local_table
        assert table.name in live, f"{table.name} missing from DB"
        declared = {c.name for c in table.columns}
        missing = declared - live[table.name]
        assert not missing, f"{table.name}: undeclared-in-DB {missing}"
```

This test is the thing that makes a dual-ORM design safe instead of a slow-motion disaster.
If someone adds a Django field and forgets the mirror, CI fails with the exact column name.

## 5. Schemas — the contract

Every response body is an explicit Pydantic v2 model. **No ORM object is ever returned raw**
— that is how you accidentally leak `internal_notes` to the public.

```python
class TattooCard(BaseModel):
    """Public list representation. Note: no price range, no artist_notes."""
    model_config = ConfigDict(from_attributes=True)
    title: str
    slug: str
    style_names: list[str]
    placement: str
    is_color: bool
    primary_image: ImageRef | None
    href: str

class TattooDetail(TattooCard):
    description: str
    artist_notes: str | None
    size_cm: str | None
    duration_minutes: int | None
    price_from: Decimal | None
    price_to: Decimal | None
    currency: str
    images: list[ImageRef]
    related: list[TattooCard]

class Page[T](BaseModel):
    items: list[T]
    page: int
    page_size: int
    total: int
    next: str | None
```

**Public vs internal separation is enforced by type.** `Booking` has two schemas:
`BookingPublic` (reference, status, created_at — what the client may see) and
`BookingArtist` (everything, artist-only). `internal_notes` exists only on the latter.

## 6. Availability service — the correctness core

```python
# services/availability.py  — framework-free, imported by Django AND FastAPI
@dataclass(frozen=True)
class Slot:
    start: datetime   # tz-aware
    end: datetime
    available: bool
    reason: str | None   # "booked" | "blocked" | "outside_hours" | None

def compute_slots(*, day: date, availability: list[AvalRow],
                  blocked: list[BlockedRow], booked: list[ApptRow],
                  now: datetime, lead_hours: int = 24) -> list[Slot]:
```

Rules implemented **once**, here, and nowhere else:
1. The weekday must have an active `Availability` row; else the day is closed.
2. Any `BlockedDate` (full-day, or partial range) removes the intersecting slots.
3. Any `Appointment` with status `scheduled|confirmed` removes its overlap.
4. Slots inside `lead_hours` from now are unavailable (no same-day bookings).
5. Slots are returned as fixed `slot_minutes` slices aligned to the window start.
6. Timezone: `Europe/…` from settings; all datetimes stored tz-aware in Postgres.

**Overlap correctness is defended twice:**
- Application: this function, with a clear user-facing reason per slot.
- Database: the `EXCLUDE USING gist (tsrange(start_at, end_at) WITH &&)` constraint on
  `Appointment`, which makes a race-condition double-booking *impossible* even if two
  requests pass the app check simultaneously. The app check gives good errors; the DB
  constraint gives truth.

## 7. Rate limiting & security

- In-process token bucket keyed by client IP + route, applied to `POST /bookings`,
  `POST /contact`, `POST /concept`. No Redis needed — single-process deployment, and the
  limit is abuse-prevention, not fair-share scheduling.
- Upload limits: `MAX_UPLOAD_MB` enforced before reading the body; Pillow `verify()` on
  every image; extension **and** MIME **and** magic-byte agreement required; SVG rejected.
- CORS: explicit allow-list from `CORS_ALLOWED_ORIGINS`. Never `*` with credentials.
- `GET /bookings/{reference}` requires the reference **and** a matching email in the query —
  reference codes are random, never sequential, so the endpoint is not enumerable.
- Security headers set in middleware: `X-Content-Type-Options`, `Referrer-Policy`,
  `X-Frame-Options: DENY`, and a strict `Content-Security-Policy` report-only in dev,
  enforcing in prod.
- No endpoint accepts arbitrary SQL-affecting parameters; ordering is validated against an
  allow-list of column names (`ordering` is a literal enum, not free text).

## 8. Caching

Content read endpoints set `Cache-Control: public, max-age=300, stale-while-revalidate=600`
plus a `Vary: Accept-Encoding`. Content mutations are rare and artist-driven, so a 5-minute
public cache is safe and makes the API effectively free under load. The image endpoint uses
`Cache-Control: public, max-age=31536000, immutable` because its key includes a content hash.

## 9. Running it

```bash
# dev — Django :8000, FastAPI :8001
uv run uvicorn fastapi.main:app --reload --port 8001
# django
uv run python manage.py runserver 8000
```

`:8000` is Django and is the only port a human opens in a browser. `:8001` is the API. The
Django templates carry `FASTAPI_BASE_URL` so the frontend JS knows where to fetch. In
production both run behind one reverse proxy: `/api/v1/*` → FastAPI, everything else → Django.
From the outside there is one origin, which is why CORS is a dev-only concern.

## 10. What the artist never sees

FastAPI is invisible in the product. There is no FastAPI-branded admin, no swagger link in
the UI, no API docs in the navigation. It is infrastructure for the frontend and for the
future, and it should feel like it does not exist — because for the artist, it doesn't.
