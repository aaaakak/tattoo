# Implementation Plan — TattoWeb

> **STATUS: Phases 0–12 complete.** See README.md for the final state, how to run the
> project, and the verification results. This document remains as the specification that
> was implemented.


Twelve phases. Each phase ends with a **verification gate**: `manage.py check`, migrations
applied cleanly, tests passing, and a real HTTP request against the running server. A phase
is not "done" because code was written — it is done when it has been exercised.

Rule observed throughout: **do not generate the whole codebase in one operation.** Each phase
is a working, running increment.

---

## PHASE 0 — Architecture (this document set) ✔ COMPLETE

Deliverables: `visual-analysis.md`, `design-system.md`, `architecture.md`, `erd.md`,
`django-apps.md`, `url-map.md`, `fastapi.md`, `components.md`, `pages.md`,
`implementation-plan.md`, `README.md`, plus `reference/` (the five verified screenshots).

Gate: the five references are located, hash-verified, measured, and analysed; the design
system is derived from measured values; the schema is specified before any model is written.

---

## PHASE 1 — Project foundation

1. `uv venv --python 3.13` and `pyproject.toml` with pinned Django 5.2, DRF, psycopg[binary],
   django-environ, Pillow, django-ratelimit, fastapi, uvicorn, sqlalchemy 2, pydantic v2,
   pydantic-settings, pytest, pytest-django, ruff.
2. Create Postgres role/database `tattoweb` (uses the existing local PG 15 instance).
3. `config/settings/{base,dev,test,prod}.py`, split; env-var driven via `django-environ`.
4. `.env.example` committed, `.env` gitignored, `.gitignore` covering venv/media/static built.
5. Django project skeleton + the nine apps created with `startapp`.
6. `templates/base/` with `base.html`, `head.html`, `header.html`, `footer.html`, `grain.html`.
7. `static/css/` architecture: `tokens.css` → `base.css` → `layout.css` → `components.css` →
   `pages.css`, imported in that order. Tokens are the design-system values verbatim.
8. `static/js/main.js` as an ES-module entry, empty module registry.
9. A `/healthz/` view returning JSON, and a smoke test asserting HTTP 200.

**Gate:** `uv run python manage.py check` clean; `migrate` applies; `runserver` serves a
styled placeholder page at `:8000`; `/healthz/` returns 200; pytest green.

---

## PHASE 2 — Models + migrations

1. `core`: abstract bases (`TimeStampedModel`, `PublishableModel`, `SEOMixin`,
   `SingletonModel`), `MediaAsset`, `Tag`, `SocialLink`, `SiteSettings`, `PublishedManager`.
2. `artists`: `ArtistProfile`, `Statistic`.
3. `tattoos`: `TattooStyle`, `Tattoo`, `TattooImage` (incl. the partial unique index).
4. `artworks`: `ArtworkCategory`, `Artwork`, `ArtworkImage`.
5. `gallery`: `GalleryCollection`, `GalleryImage` (incl. the exactly-one-provenance CHECK).
6. `clients`: `Client` (partial unique on non-empty email).
7. `booking`: `Availability`, `BlockedDate`, `Booking`, `BookingReference`, `Appointment`
   — **including `CREATE EXTENSION btree_gist` and the `EXCLUDE USING gist` constraint.**
8. `shop`: `ProductCategory`, `Product`, `ProductImage`, `Order`, `OrderItem`.
9. `contact`: `ContactMessage`. `core` also gains `ConceptRequest` (inert).
10. Add the `search_vector` generated columns + GIN indexes via `RunSQL` in a migration.
11. `tests/test_models.py`: singleton enforcement, slug auto-generation without overwriting,
    the price-range CHECK, the primary-image partial unique, and the
    **double-booking EXCLUDE constraint** (create overlapping appointments, assert
    `IntegrityError`) — this test is the most important in the suite.

**Gate:** all migrations apply to a **freshly dropped** database with no errors; the
double-booking test genuinely raises `IntegrityError`; `makemigrations --check` reports no
pending changes.

---

## PHASE 3 — Image pipeline + admin (CMS)

1. `services/images.py`: derivative generation (`_800`, `_1200`, `_1600`, `_2400` WebP),
   LQIP blur placeholder, and `services/dither.py`: the ordered-dither (Bayer 8x8)
   generator producing the cobalt-on-black sibling. Pure Pillow, no framework imports.
2. Wire generation into `MediaAsset.save()` and a `backfill_derivatives` management command.
3. Upload validation: extension + MIME + magic-byte + Pillow `verify()` + size cap; UUID paths.
4. `admin.py` for all nine apps: `list_display` on real fields, `list_filter`, `search_fields`,
   `autocomplete_fields`, `fieldsets`, image inlines with ordering, `list_editable` on
   `status`/`is_featured`/`order`, `save_on_top`.
5. A custom `AdminSite` header with the artist's branding (not "Django administration").
6. Optional but included: a simple artist dashboard on the admin index showing open bookings,
   unread messages and low-stock products.

**Gate:** create a Tattoo and an Artwork through the admin with real uploaded images;
confirm derivatives **and** the dither sibling exist on disk; confirm the admin list pages
filter and search correctly; confirm a 50MB file and an SVG are both rejected.

---

## PHASE 4 — Public site structure

1. Context processor supplying `nav_items`, `site_settings`, `artist` to all templates.
2. `base.html` complete: header with glass-on-scroll, full-screen mobile menu, footer,
   grain overlay, page-transition overlay.
3. All page templates created as **structurally complete but content-light** shells, so
   navigation works end-to-end from the first day:
   `home`, `tattoos/list`, `tattoos/detail`, `tattoos/styles`, `artworks/list`,
   `artworks/detail`, `gallery/index`, `gallery/collection`, `about`, `booking/form`,
   `booking/success`, `shop/list`, `shop/detail`, `contact`, `errors/{404,500}`.
4. `DesignSystem` reference page at `/design-system/` (staff-only, `DEBUG`-gated): renders
   every token, type style and component state. This is how the visual system is verified
   rather than eyeballed.
5. `tests/test_smoke_pages.py`: every URL in the map returns its expected status code with an
   empty database, and with a seeded one.

**Gate:** every link in the header and footer resolves; no 500s anywhere; 404 and 500 pages
are styled and on-brand; the design-system page renders in both themes at 320/768/1440.

---

## PHASE 5 — Homepage

1. Hero: `HeroCanvas` with real CMS data — kicker, display statement, CTAs, hero image with
   parallax, and the **frame-breakout** composition.
2. Artist introduction: statement ("INK IS ONLY THE MEDIUM."), a capped excerpt of the
   biography, portrait, and the `StatRow` (10+ / 1200+ / 08 / 01) with a once-only count-up.
3. Featured tattoo run and featured artwork run using `EditorialRun` (3-column, fixed order).
4. Styles strip: mono-indexed style chips from the CMS with counts.
5. Booking-availability strip: mono line stating the next open dates, from the availability
   service (real data, not a hard-coded string).
6. `DisplayStatement` line reveal + `DitherImage` resolve wired and tuned.
7. Homepage is **100% CMS-driven** — zero hard-coded business content. Every element has an
   admin source and a documented fallback.

**Gate:** every element on the homepage renders from seeded CMS data; edit a headline in the
admin, refresh, and see the change; Lighthouse desktop ≥ 95 performance with real images.

---

## PHASE 6 — Tattoo, artwork and gallery systems

1. Paginated, filterable tattoo list with `FilterRail` (style, placement, colour) — links, not
   JS-only. `select_related`/`prefetch_related` verified and asserted with `assertNumQueries`.
2. Tattoo detail: hero image, `Lightbox` gallery, `SpecTable`, artist notes, styles, related works.
3. Style index and style detail pages with counts.
4. Artwork list with category/year/availability filters; artwork detail sharing the tattoo
   detail visual grammar but with medium/dimensions/year/edition instead of placement/size/duration.
5. Gallery: `MasonryRun` with explicit aspect ratios, collection pages, `Lightbox` with full
   keyboard + touch support, filter by collection and featured.
6. Featured flags respected on list views; cheap `only()` card querysets.

**Gate:** 200 seeded records paginate and filter correctly; gallery lightbox is fully keyboard
navigable; **no list view exceeds its query budget** (asserted by test); zero layout shift on
image load at all seven breakpoints.

---

## PHASE 7 — Booking, availability, clients

1. `services/availability.py` implemented and unit-tested **before** any view touches it
   (closed weekdays, blocked dates, partial-day blocks, existing appointments, lead time,
   timezone boundaries).
2. Booking form: all client fields, multi-image `FileDropZone`, server-side validation,
   CSRF, rate limit, honeypot + timing check, `Booking` + `Client` (reuse by email) +
   `BookingReference` rows created in one transaction.
3. Reference code generation (unambiguous alphabet, no `0/O/1/I`), uniqueness retried.
4. Success page showing the reference, plus an email-ready service function (sending is
   config-gated, and logged when unconfigured rather than silently pretending).
5. `AvailabilityCalendar` bound to `/api/v1/availability/days`; selecting a day filters slots.
6. Admin booking workflow: list with status/date filters, inline references with thumbnails,
   status transitions, appointment creation with **server-side overlap validation** that
   surfaces the DB constraint as a friendly form error rather than a 500.
7. Client list/detail showing booking and appointment history.
8. `tests/test_booking_rules.py`: the full matrix of the availability function, plus a
   **concurrent-booking test** proving the constraint holds under two simultaneous inserts.

**Gate:** submit a booking through the real form with 3 images; it appears in admin; approve
and schedule it; confirm the slot disappears from availability; attempt a manual overlapping
appointment and get a validation error, not a crash. JS disabled: the form still submits.

---

## PHASE 8 — Shop

1. Product catalogue with category/type/availability filters; made-to-order vs in-stock
   distinctions rendered honestly; sold-out products remain visible but not orderable.
2. Product detail with `Lightbox`, edition info, shipping accordion.
3. `Order`/`OrderItem` present in the schema and admin, **no** checkout, **no** provider.
4. A `PaymentProvider` protocol (abstract) with a `NullProvider` implementation and a
   `checkout_service.py` that returns "not configured" — the extension point Stripe will
   satisfy, with no dead code pretending to charge anything.

**Gate:** catalogue filters work; adding a product via admin appears on the site; the
unsupported checkout path fails loudly and clearly; no provider names appear in the UI.

---

## PHASE 9 — FastAPI

1. `fastapi/main.py` app factory, lifespan-managed engine, SQLAlchemy mirrors,
   contract test from `fastapi.md` §4.
2. Routers: tattoos, styles, artworks, gallery, products, search, site, availability,
   bookings, contact, images, meta, concept (501).
3. Pydantic v2 schemas with strict public/internal separation (`internal_notes` unreachable).
4. Pagination, filtering, ordering via a validated allow-list; consistent error envelope.
5. Availability and booking routers calling the **shared** `services/availability.py`.
6. Image endpoint with whitelisted widths, format negotiation and immutable cache headers.
7. Rate limiting on the three write routes; CORS allow-list; security headers.
8. `tests/test_api.py` (httpx `ASGITransport`) + `tests/test_schema_contract.py`.

**Gate:** all endpoints return schema-valid JSON against seeded data; OpenAPI generates;
contract test passes; `POST /bookings` from the API produces a record identical to the Django
form path (same service function asserted by test); a booking reference cannot be enumerated.

---

## PHASE 10 — Motion and visual polish

1. `reveal.js` (IntersectionObserver, unobserve after fire), `resolve.js` (dither→full),
   `parallax.js` (hero only, rAF, transform-only), `lightbox.js`, `cursor.js`
   (`pointer: fine` only), `transition.js` (cobalt wipe), `forms.js` (progressive enhancement).
2. Every module: no-op under `prefers-reduced-motion`; every module detaches its listeners;
   nothing animates on `width`/`top`/`filter` in a loop.
3. Page transitions: intercept same-origin navigations only; always allow
   `target="_blank"`, modifier-clicks and back/forward to behave natively.
4. Cursor interactions: a small cobalt ring on desktop, **never** hiding the native cursor
   and **never** applied to form inputs.
5. Visual QA of the dither↔full transition across 12 real images in both themes; tune the
   dither threshold per image class (dark tattoos vs high-key paintings need different
   thresholds — this is a per-asset field, not a global constant).
6. Total JS budget verified under 30KB minified.

**Gate:** smooth on a 2019-class laptop at 1440p; no layout shift; JS budget met; the site is
fully usable and attractive with JS disabled; reduced-motion mode is genuinely static.

---

## PHASE 11 — SEO, security, performance

1. `SEOMixin` fallback chain wired into `head.html`: title, description, canonical, OG, Twitter
   cards, and JSON-LD (`Person` for the artist, `ImageObject`/
   `CreativeWork` for tattoos and artworks, `Product` for shop items, `BreadcrumbList` omitted
   by design).
2. Sitemaps per section + `robots.txt`; `noindex` for `/booking/success/`, drafts and admin.
3. Structured data validated against the schema test tools; canonical URLs absolute and stable.
4. `SlugHistory` redirect table so a renamed slug 301s instead of 404ing — protecting
   indexed URLs.
5. Security pass: `manage.py check --deploy` clean in prod settings; secure cookies, HSTS,
   `SECURE_SSL_REDIRECT`, `X_FRAME_OPTIONS=DENY`; `tests/test_secrets.py` asserting no
   secret literals in the tree, that `.env` is ignored and untracked, and that
   `config.settings.prod` refuses to boot without a secret key; confirmed `DEBUG=False`
   behaviour with static files.
6. Performance pass: query counts asserted per view; `django-debug-toolbar` in dev only;
   static hashing + long cache headers; database indexes reviewed with `EXPLAIN ANALYZE`
   on the three heaviest queries; hero image preloaded with `fetchpriority="high"`.

**Gate:** Lighthouse ≥95 performance / ≥95 accessibility / 100 SEO on home, tattoo detail and
artwork detail (mobile + desktop); `check --deploy` reports zero warnings; no N+1 anywhere.

---

## PHASE 12 — Testing and production readiness

1. Full test suite: models, services, booking rules, API, contract, smoke pages, security,
   accessibility basics (every image has `alt`, every form has labels, every interactive
   element is keyboard reachable — asserted by test, not by hope).
2. Coverage report; the availability service, booking flow and image pipeline at 100%.
3. `Dockerfile` + `docker-compose.yml` (Postgres + Django via gunicorn/uvicorn + FastAPI)
   for deployment **only** — local dev stays native, because Postgres is already native here.
4. Sample systemd/launchd units for both processes behind Caddy/nginx, with
   `/api/v1/*` → FastAPI and everything else → Django.
5. `seed_demo` management command producing a realistic demo dataset (12 styles, 40 tattoos,
   30 artworks, 60 gallery images, 8 products, 5 bookings across every status) — this is what
   makes the site demonstrable without the artist's personal work.
6. Backup/restore documented for media + Postgres; a `dumpdata`/`loaddata` fixture path.
7. README completed with verified commands (every command in the README must have been run).

**Gate:** fresh clone → documented commands → running site with seeded data, with no step
missing and no command that fails. Suite green. `check --deploy` clean.

---

## Post-MVP (explicitly deferred, architected for)

- Stripe checkout behind the `PaymentProvider` protocol
- Google Calendar two-way sync using `Appointment.calendar_event_id`
- AI concept generation at `/api/v1/concept`, always labelled **CONCEPT ART**, never
  presented as performed work
- Client self-service portal (currently the artist manages everything from admin)
- Celery + Redis — **trigger condition:** the first genuinely asynchronous job
  (order emails, Stripe webhooks, bulk AI generation). Not before.

## Working agreement

Phases are sequential. Each gate must pass before the next phase begins — no exceptions, and
no "I'll fix it in the next phase." If a gate fails, the phase is not done. At the end of each
phase I report: what was built, the exact commands run, their real output, and what is next.
