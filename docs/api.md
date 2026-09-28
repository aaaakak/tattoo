# API Reference — TattoWeb

Base URL: `http://127.0.0.1:8001/api/v1`
Interactive docs: `/api/v1/docs` (Swagger UI) · `/api/v1/redoc` · `/api/v1/openapi.json`

Served by FastAPI. Django renders the site; this is the service layer only.

---

## Design rules

1. **Read-mirrors, never DDL.** Django migrations own the schema. The SQLAlchemy models in
   `api_service/db/models.py` are read mirrors, and `tests/test_api.py::test_sqlalchemy_mirrors_match_the_live_database`
   asserts every declared column exists in Postgres. A Django field addition that is not
   mirrored fails CI naming the exact column.
2. **No raw ORM dumps.** Every response is an explicit Pydantic model, so private fields
   (`artist_notes`, `internal_notes`, client contact details) cannot leak by accident.
3. **Shared business rules.** Booking creation and availability call the same functions in
   `services/` that the Django views use. The two paths cannot diverge.
4. **Pagination is uniform.** Every list endpoint returns the same envelope.

### Pagination envelope

```json
{ "items": [...], "page": 1, "page_size": 24, "total": 12, "pages": 1,
  "next": null, "previous": null }
```

`page_size` is capped at 100. Requests above that return `422`.

---

## Content

| Method | Path | Description |
|---|---|---|
| GET | `/tattoos` | List tattoos. Filters: `style`, `placement`, `is_color`, `featured`, `q` |
| GET | `/tattoos/{slug}` | Full detail incl. all images and the artist notes |
| GET | `/styles` | All tattoo styles with published piece counts |
| GET | `/styles/{slug}` | Style detail |
| GET | `/categories` | Artwork categories |
| GET | `/artworks` | List artwork. Filters: `category`, `year`, `availability`, `featured`, `q` |
| GET | `/artworks/{slug}` | Artwork detail |
| GET | `/gallery` | Gallery images. Filters: `featured`, `limit` |
| GET | `/products` | Shop items. Filters: `category`, `product_type`, `availability`, `featured` |
| GET | `/products/{slug}` | Product detail |

List endpoints omit private fields. `artist_notes` appears **only** on the tattoo detail
endpoint, and a test asserts it never appears in a list payload.

### Images

Every image reference carries both variants:

```json
{ "url": "/media/2026/09/abc.png",
  "dither_url": "/media/2026/09/abc__dither.webp",
  "width": 1024, "height": 1024, "alt": "…" }
```

`dither_url` is the pre-generated halftone plate. It is `null` when no plate exists, so a
client must handle that case rather than assuming it is always present.

---

## Site

| Method | Path | Description |
|---|---|---|
| GET | `/site` | Site settings, artist identity, contact details, booking switch |

Contains public identity fields only. A test asserts no credential-shaped key appears.

---

## Availability

| Method | Path | Description |
|---|---|---|
| GET | `/availability?year=&month=` | Which dates in a month have any bookable slot |
| GET | `/availability/{date}` | Every slot for one date, each with a state |

Slot states: `available`, or a reason — `booked`, `blocked`, `too_soon`.

Computed by `services/availability.py`, which is framework-free and shared with the Django
views. Slots respect working hours, blocked dates, existing appointments, and a 24-hour
minimum lead time.

---

## Booking

| Method | Path | Description |
|---|---|---|
| POST | `/bookings` | Submit a request. Rate-limited: 5/hour per client |
| GET | `/bookings/{reference}?email=` | Look up a request |

**`GET /bookings/{reference}` requires both the reference and the matching email.** A
reference alone reveals nothing, which makes the endpoint non-enumerable. A wrong
reference and a wrong email return byte-identical responses, so the error cannot be used
to test whether a booking exists.

Statuses: `new`, `reviewing`, `potential`, `approved`, `scheduled`, `completed`,
`cancelled`, `rejected`.

### POST /bookings

```json
{
  "name": "…", "email": "…", "phone": "…",
  "style_slug": "blackwork", "placement": "Forearm",
  "approx_size": "12 x 18 cm", "is_color": "black_grey",
  "description": "…", "budget_min": 200, "budget_max": 500,
  "preferred_date": "2026-10-06", "preferred_time": "morning",
  "contact_consent": true
}
```

Validation: description ≥ 10 characters, `contact_consent` must be true, `budget_max` ≥
`budget_min`, email must be valid. A past or over-one-year-ahead date is rejected, and a
date with no availability is refused with a readable message.

---

## Search

| Method | Path | Description |
|---|---|---|
| GET | `/search?q=` | Cross-entity search: tattoos, styles, artwork, products |

Minimum query length is 2 characters. Results are grouped by type with per-group counts.
No matches returns `200` with `total: 0`, never an error.

---

## Contact

| Method | Path | Description |
|---|---|---|
| POST | `/contact` | Submit a message. Rate-limited: 5/hour per client |

---

## Meta

| Method | Path | Description |
|---|---|---|
| GET | `/healthz` | Liveness, includes a database check |
| GET | `/meta` | Version and schema-ownership metadata |

---

## Caching

Content endpoints send:

```
Cache-Control: public, max-age=300, stale-while-revalidate=600
```

Content changes are artist-driven and rare, so a five-minute public cache is safe.

---

## Security

- CORS: explicit allow-list from `CORS_ALLOWED_ORIGINS`. Never `*` with credentials.
- Rate limiting on `POST /bookings` and `POST /contact` (in-process sliding window).
- Security headers: `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`.
- The generic exception handler logs the detail and returns a stable error shape —
  a traceback is never sent to a client.
- `ordering` and filters are validated, never interpolated into SQL.

**Known limitation, stated deliberately:** rate limiting is in-process. A multi-process or
multi-host deployment needs a shared store; the current design is correct for a single
process and is not an oversight.

---

## Running

```bash
uv run uvicorn api_service.main:app --reload --port 8001
```

In production a single reverse proxy fronts both stacks: `/api/v1/*` → FastAPI,
everything else → Django. One public origin, which is why CORS is a dev-only concern.
