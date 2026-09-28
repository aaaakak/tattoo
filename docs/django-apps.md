# Django Apps — TattoWeb

Nine apps plus a DRF package. Each exists because it has a distinct **owner, lifecycle and
reason to change**. The test applied to every boundary: *would a change to X ever force a
change to Y for an unrelated reason?* If yes, they are separate apps. If no, they are merged.

Why not one giant app: `tattoos`, `artworks` and `shop` share an image pattern but have
different fields, different admin needs and different publication rules. Merging them would
mean one 1,500-line `models.py` and conditional admin — a maintenance trap.

Why not dozens of micro-apps: `TattooImage` has no life without `Tattoo`; a
`tattoo_images` app would add a migration dependency and import ceremony for zero isolation.
Same for `BookingReference` under `booking`, and `ProductImage` under `shop`.

---

## `apps/core`
**Owns:** `SiteSettings`, `SocialLink`, `MediaAsset`, `Tag`, `TimeStampedModel`,
`SEOMixin`, `SingletonModel` abstract bases, context processors, template tags, and the
`sitemap.py` / `robots.txt` views.
**Exists because:** every other app needs shared abstractions and site-wide singletons.
If these lived in `tattoos`, the shop would import from a tattoo app — an absurd dependency.
**Depends on:** nothing.

## `apps/artists`
**Owns:** `ArtistProfile`, `Statistic`.
**Exists because:** the artist's identity (statement, biography, portrait, stats, contact,
booking switch) is edited on its own cadence and is consumed by *every* page. It is not
tattoo data.
**Depends on:** `core`.

## `apps/tattoos`
**Owns:** `TattooStyle`, `Tattoo`, `TattooImage`.
**Exists because:** the tattoo catalogue is the primary product surface, with its own
fields (placement, size, duration, price range, color/black-grey), its own admin workflow
and its own public pages.
**Depends on:** `core`, `artists` (for the byline).

## `apps/artworks`
**Owns:** `ArtworkCategory`, `Artwork`, `ArtworkImage`.
**Exists because:** artwork is *not* a tattoo category. Different fields (medium, dimensions,
year, edition, availability), different presentation (gallery-object framing, not
body-placement metadata), and a different edit cadence. The brief explicitly forbids
collapsing it into the tattoo system.
**Depends on:** `core`.

## `apps/gallery`
**Owns:** `GalleryCollection`, `GalleryImage`.
**Exists because:** the gallery is a **curation layer over** existing media, not a third
content type. It references `TattooImage` and `ArtworkImage` by nullable one-to-one and
carries its own layout metadata (`aspect`, `span`, `order`) that belongs to neither parent.
Putting `span` on `TattooImage` would leak gallery concerns into the tattoo domain.
**Depends on:** `core`, `tattoos`, `artworks`.

## `apps/clients`
**Owns:** `Client`.
**Exists because:** the client is a person with a lifetime relationship across bookings,
appointments and notes. Bookings must survive independently of clients, and clients must be
`PROTECT`ed from casual deletion. A distinct app makes that ownership explicit and prevents
the booking app from quietly becoming a CRM.
**Depends on:** `core`.

## `apps/booking`
**Owns:** `Availability`, `BlockedDate`, `Booking`, `BookingReference`, `Appointment`,
plus `services.py` wrappers over the shared availability engine.
**Exists because:** the booking workflow (request → review → approve → schedule → complete)
is the most logic-dense part of the site, with its own state machine and the hardest
correctness requirement (no double-booking). It deserves isolation and its own test module.
**Depends on:** `core`, `clients`, `tattoos` (style FK).

## `apps/shop`
**Owns:** `ProductCategory`, `Product`, `ProductImage`, and the `Order` / `OrderItem`
skeleton.
**Exists because:** commerce has its own rules (stock, editions, price snapshotting into
orders) and its own future (Stripe). Keeping `Order` away from `Booking` means a payment
integration can never touch the booking state machine.
**Depends on:** `core`.

## `apps/contact`
**Owns:** `ContactMessage`.
**Exists because:** it is a single genuinely independent concern: an inbound message queue
for the artist, unrelated to bookings, with its own read/replied lifecycle.
**Depends on:** `core`.

## `apps/accounts`
**Owns:** artist authentication glue — a custom `User` passthrough if needed,
`ArtistRequiredMixin`, permission groups (`artist`, `staff`), the login/logout views styling,
and the password-change flow.
**Exists because:** authorisation policy should be declared once, in one importable place,
rather than re-derived in each app's views. Small by design.
**Depends on:** `core`.

## `api/` (DRF package, not an app)
**Owns:** Django-side read serializers, viewsets and routers for content that Django
should serve as JSON (sitemap-adjacent data, admin-token endpoints).
**Exists because:** DRF is the natural way to expose Django models as JSON without
re-implementing them in SQLAlchemy. It is *not* a Django app because it has no models.
**Boundary:** DRF serves **authenticated administrative and aggregate** JSON.
FastAPI serves the **public, cacheable, high-traffic** API. See `fastapi.md`.

---

## App dependency graph

```
core ◄── artists
  ▲        ▲
  │        │
  │   ┌────┴────┬────────┐
  │   │         │        │
  │ tattoos  artworks  shop
  │   ▲        ▲        ▲
  │   │        │        │
  │   └── gallery ──────┘
  │
 clients
  ▲
  │
 booking ──► tattoos (style FK)

contact  (independent)
accounts (cross-cutting, imported by all views)
```

No cycles. `core` is a leaf that depends on nothing. `gallery` is the only app that
depends on two content apps, which is correct — its whole job is curation across them.

---

## Abstract base classes (in `apps/core/models.py`)

```python
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True

class PublishableModel(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"
    status = models.CharField(max_length=20, choices=Status.choices,
                              default=Status.DRAFT, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        abstract = True

    def publish(self):
        self.status = self.Status.PUBLISHED
        self.published_at = self.published_at or timezone.now()
        self.save(update_fields=["status", "published_at"])

class SEOMixin(models.Model):
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.CharField(max_length=320, blank=True)
    og_image = models.ForeignKey("core.MediaAsset", null=True, blank=True,
                                 on_delete=models.SET_NULL,
                                 related_name="+")
    class Meta:
        abstract = True

    def get_meta_title(self, fallback: str = "") -> str:
        return self.meta_title or fallback

    def get_meta_description(self, fallback: str = "") -> str:
        return self.meta_description or fallback
```

## Custom managers

Every content app defines a `PublishedManager` exposing `.published()` — so no view ever
writes `filter(status="published")` by hand, and a future change to publication rules
is a one-line edit.

```python
class PublishedManager(models.Manager):
    def published(self):
        return (self.get_queryset()
                .filter(status="published", published_at__lte=timezone.now()))
```

## Service layer rule

**Business logic never lives in a view, a serializer or a template.**
- Shared, framework-free logic → top-level `services/` (importable by Django *and* FastAPI):
  `availability.py`, `images.py`, `seo.py`, `dither.py`.
- App-specific orchestration → `apps/<app>/services.py`
  (e.g. `booking/services.py: create_booking_from_payload()`), called by views.

Templates receive already-shaped data. If a template needs to compute something, that is a
missing service or a missing `@property`.

## Admin rule

Every app ships a `admin.py` with:
`list_display` on real columns (never `__str__`), `list_filter`, `search_fields`,
`autocomplete_fields` for FKs (prevents 10k-row `<select>`), `fieldsets` grouping,
`readonly_fields = (created_at, updated_at)`, and inlines for child images with
`sortable` ordering. `save_on_top = True` and `list_editable` where genuinely useful
(status, is_featured, order).
