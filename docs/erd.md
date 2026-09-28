# ERD — TattoWeb

PostgreSQL 15. All tables `snake_case`. Every model gets `id BIGSERIAL PK`,
`created_at TIMESTAMPTZ`, `updated_at TIMESTAMPTZ` (via an abstract `TimeStampedModel`)
unless noted. Delete behaviour is stated explicitly per relation because getting this wrong
destroys an artist's portfolio.

Legend: `1─*` one-to-many · `*─*` many-to-many · `1─1` one-to-one ·
`CASCADE` delete children · `PROTECT` refuse delete while children exist · `SET_NULL` orphan.

---

## Diagram (text)

```
ArtistProfile 1─1 auth.User
ArtistProfile 1─* Statistic
ArtistProfile *─* SocialLink  (via artist socials)

TattooStyle 1─* Tattoo
Tattoo *─* TattooStyle      (mm: styles — a piece can be blackwork + ornamental)
Tattoo 1─* TattooImage

ArtworkCategory 1─* Artwork
Artwork 1─* ArtworkImage
Tattoo *─* Artwork          (mm: "related works" cross-linking, SET_NULL-safe)

GalleryCollection 1─* GalleryImage
GalleryImage *─1 TattooImage? / ArtworkImage?   (nullable generic link)

Client 1─* Booking
Client 1─* Appointment
Booking 1─* BookingReference
Booking *─1 TattooStyle
Booking 1─1 Appointment         (nullable until scheduled)
Appointment *─1 Availability

Availability (recurring weekly template, per weekday)
BlockedDate (explicit date overrides)

ProductCategory 1─* Product
Product 1─* ProductImage

ContactMessage (standalone)
SiteSettings (singleton)
ConceptRequest (future AI hook, inert)
```

---

## 1. core

### SiteSettings  *(singleton, pk=1 enforced)*
| Field | Type | Notes |
|---|---|---|
| site_name | CharField(120) | |
| tagline | CharField(200) | |
| hero_title | CharField(200) | editable homepage headline |
| hero_kicker | CharField(120) | e.g. "TATTOO ARTIST / VISUAL ARTIST" |
| hero_media | FK → core.MediaAsset, `SET_NULL`, null | |
| default_meta_description | CharField(320) | |
| og_default_image | FK → MediaAsset, `SET_NULL` | |
| contact_email / contact_phone | EmailField / CharField | |
| studio_address | TextField | |
| map_embed_url | URLField(blank) | |
| booking_open | BooleanField | master switch for the booking form |
| announcement | TextField(blank) | optional studio notice |
created_at/updated_at ✓
**Constraints:** `CHECK (id = 1)` via a `SingletonModel.save()` override + DB check.

### SocialLink
| Field | Type | Notes |
|---|---|---|
| platform | CharField(40), choices | instagram, telegram, email, behance, x |
| label | CharField(80) | display text |
| url | URLField | |
| handle | CharField(80, blank) | e.g. `@artist` |
| order | PositiveSmallIntegerField | |
| is_active | BooleanField | |
**Indexes:** `(is_active, order)`.

### MediaAsset  *(shared upload abstraction)*
| Field | Type | Notes |
|---|---|---|
| file | ImageField(upload_to=uuid_path) | |
| kind | CharField(20) | original / derivative / dither / lqip |
| width, height | PositiveIntegerField | |
| byte_size | PositiveIntegerField | |
| sha256 | CharField(64), db_index | dedupe across the whole system |
| alt_text | CharField(200, blank) | accessibility |
**Constraints:** `UNIQUE(sha256, kind)`. **Indexes:** `(kind)`, `(sha256)`.
Used by `SiteSettings.hero_media` and by `ConceptRequest`.

---

## 2. artists

### ArtistProfile  *(singleton)*
| Field | Type | Notes |
|---|---|---|
| user | OneToOne → auth.User, `SET_NULL`, null | login link |
| display_name | CharField(120) | the name in the header |
| monogram | CharField(6) | tiny logo mark |
| role_line | CharField(160) | "TATTOO ARTIST / VISUAL ARTIST" |
| statement | TextField | "INK IS ONLY THE MEDIUM." |
| biography | TextField | |
| portrait | FK → MediaAsset, `SET_NULL` | |
| location_city / location_country | CharField(80) | |
| years_experience | PositiveSmallIntegerField | |
| email / phone | EmailField / CharField | |
| is_booking_open | BooleanField | |
| meta_title / meta_description | CharField | SEO |

### Statistic  *(the 10+ / 1200+ / 08 / 01 block)*
| Field | Type | Notes |
|---|---|---|
| artist | FK → ArtistProfile, `CASCADE`, related_name='statistics' | |
| value | CharField(20) | "10+", "1200+", "08" — stored as text for exact display |
| label | CharField(60) | "YEARS", "TATTOOS", "SIGNATURE STYLES", "VISION" |
| order | PositiveSmallIntegerField | |
**Constraint:** `UNIQUE(artist, order)`. **Indexes:** `(artist, order)`.

---

## 3. tattoos

### TattooStyle
| Field | Type | Notes |
|---|---|---|
| name | CharField(80), unique | Blackwork, Fine Line, Gothic, … |
| slug | SlugField(90), unique, db_index | |
| description | TextField | |
| cover | FK → MediaAsset, `SET_NULL` | |
| is_featured | BooleanField, db_index | |
| order | PositiveSmallIntegerField | |
| seo_* | | |
**Ordering:** `(order, name)`. **Indexes:** `(is_featured, order)`.

### Tattoo
| Field | Type | Notes |
|---|---|---|
| title | CharField(160) | |
| slug | SlugField(180), unique, db_index | |
| description | TextField | |
| artist_notes | TextField(blank) | shown on detail page |
| styles | M2M → TattooStyle, related_name='tattoos' | multi-style supported |
| placement | CharField(80), db_index | Forearm, Ribs, Hand, Back… (choices, open-ended) |
| size_cm | CharField(40, blank) | text: "12 x 18 cm" |
| duration_minutes | PositiveIntegerField(null) | |
| price_from | DecimalField(9,2, null) | ranges supported via `price_to` |
| price_to | DecimalField(9,2, null) | |
| currency | CharField(3), default 'EUR' | |
| is_color | BooleanField | color vs black & grey |
| status | CharField(20), choices, db_index | draft / published / archived |
| is_featured | BooleanField, db_index | |
| published_at | DateTimeField(null), db_index | |
| session_date | DateField(null) | when it was tattooed |
| tags | M2M → core.Tag, blank, related_name='tattoos' | |
| meta_title / meta_description | SEO | |
**Constraints:** `CHECK (price_to IS NULL OR price_from IS NULL OR price_to >= price_from)`.
**Indexes:** `(status, is_featured, -published_at)`, `(slug)`, `(placement)`, GIN on a
`search_vector` generated column (title + description + tags) for FastAPI search.
**Ordering:** `(-published_at, -created_at)`.

### TattooImage
| Field | Type | Notes |
|---|---|---|
| tattoo | FK → Tattoo, `CASCADE`, related_name='images' | |
| asset | FK → MediaAsset, `PROTECT` | shared asset never dies under a live parent |
| caption | CharField(200, blank) | |
| order | PositiveSmallIntegerField | |
| is_primary | BooleanField | |
| variant | CharField(20), choices | detail / healed / process / studio |
**Constraint:** `UNIQUE(tattoo, order)`. Partial unique:
`UNIQUE(tattoo) WHERE is_primary` — guarantees exactly one primary image.
**Indexes:** `(tattoo, order)`.

---

## 4. artworks

### ArtworkCategory
| Field | Type | Notes |
|---|---|---|
| name / slug / description / cover / order / is_featured | | Paintings, Drawings, Illustration, Digital, Prints, Experimental |

### Artwork
| Field | Type | Notes |
|---|---|---|
| title | CharField(160) | |
| slug | SlugField(180), unique, db_index | |
| description | TextField | |
| category | FK → ArtworkCategory, `PROTECT`, related_name='artworks' | protected: no orphaned art |
| medium | CharField(120) | "Ink on paper", "Oil on canvas" |
| dimensions | CharField(80) | "70 x 100 cm" |
| year | PositiveSmallIntegerField, db_index | |
| availability | CharField(20), choices, db_index | available / sold / commission / private |
| price | DecimalField(9,2, null) | |
| currency | CharField(3), default 'EUR' | |
| edition_info | CharField(120, blank) | "Ed. 2/25" |
| is_featured | BooleanField, db_index | |
| status | CharField(20), choices, db_index | draft / published / archived |
| published_at | DateTimeField(null) | |
| tags | M2M → core.Tag, blank | |
| meta_* | SEO | |
**Indexes:** `(status, is_featured, -year)`, `(category, status)`, `(slug)`, GIN search_vector.

### ArtworkImage  *(same shape as TattooImage, FK → Artwork)*

---

## 5. gallery

### GalleryCollection
| Field | Type | Notes |
|---|---|---|
| title / slug / description | | Curated sets: "INK STUDIES", "2026 SELECTED" |
| is_featured | BooleanField, db_index | |
| order | PositiveSmallIntegerField | |
| cover | FK → MediaAsset, `SET_NULL` | |

### GalleryImage
| Field | Type | Notes |
|---|---|---|
| collection | FK → GalleryCollection, `CASCADE`, related_name='images', null | null = uncollected |
| asset | FK → MediaAsset, `PROTECT` | |
| tattoo_image | OneToOne → TattooImage, `SET_NULL`, null | optional provenance link |
| artwork_image | OneToOne → ArtworkImage, `SET_NULL`, null | optional provenance link |
| caption | CharField(200, blank) | |
| aspect | CharField(10) | portrait / landscape / square — drives masonry without layout thrash |
| span | PositiveSmallIntegerField, default 1 | grid span for asymmetric layout |
| is_featured | BooleanField, db_index | |
| order | PositiveSmallIntegerField | |
**Constraint:** `CHECK (NOT (tattoo_image IS NOT NULL AND artwork_image IS NOT NULL))`
— an image has one provenance, not two.
**Indexes:** `(collection, order)`, `(is_featured, order)`.

---

## 6. clients

### Client
| Field | Type | Notes |
|---|---|---|
| name | CharField(160), db_index | |
| slug | SlugField(180), unique | admin-friendly URL |
| email | EmailField(db_index, blank) | |
| phone | CharField(40, blank) | |
| instagram | CharField(80, blank) | |
| telegram | CharField(80, blank) | |
| notes | TextField(blank) | artist's private notes |
| preferences | TextField(blank) | style preferences |
| is_vip | BooleanField | |
| tags | M2M → core.Tag, blank | |
**Constraints:** `UNIQUE(email) WHERE email <> ''`. **Indexes:** `(name)`, `(email)`.
**Delete behaviour:** deleting a Client is `PROTECT`ed while Bookings exist — the artist must
archive, not erase, history.

---

## 7. booking

### Availability  *(recurring weekly template)*
| Field | Type | Notes |
|---|---|---|
| weekday | PositiveSmallIntegerField, choices 0-6 | |
| start_time / end_time | TimeField | |
| slot_minutes | PositiveSmallIntegerField, default 60 | |
| is_active | BooleanField | |
**Constraint:** `UNIQUE(weekday, start_time)`, `CHECK (end_time > start_time)`.

### BlockedDate
| Field | Type | Notes |
|---|---|---|
| date | DateField, db_index | |
| end_date | DateField(null) | ranges supported |
| reason | CharField(160, blank) | |
| all_day | BooleanField, default True | |
| start_time / end_time | TimeField(null) | partial-day block |
**Constraint:** `CHECK (end_date IS NULL OR end_date >= date)`.
**Indexes:** `(date)`, `(date, end_date)`.

### Booking
| Field | Type | Notes |
|---|---|---|
| reference | CharField(12), unique, db_index | human code, e.g. `TW-7K3F9A` |
| client | FK → Client, `PROTECT`, related_name='bookings' | created/reused on submit |
| style | FK → TattooStyle, `SET_NULL`, null | requested style |
| placement | CharField(80) | |
| approx_size | CharField(40) | |
| is_color | CharField(10), choices | color / black_grey / undecided |
| description | TextField | |
| budget_min / budget_max | DecimalField(9,2, null) | |
| status | CharField(20), choices, db_index | new, reviewing, potential, approved, scheduled, completed, cancelled, rejected |
| preferred_date | DateField(null) | client's wish |
| preferred_time | CharField(20, blank) | morning / afternoon / evening |
| internal_notes | TextField(blank) | artist only |
| contact_consent | BooleanField | GDPR |
| source | CharField(20) | web / admin / instagram |
**Constraints:** `CHECK (budget_max IS NULL OR budget_min IS NULL OR budget_max >= budget_min)`.
**Indexes:** `(status, -created_at)`, `(preferred_date)`, `(client)`.
**Ordering:** `-created_at`.

### BookingReference  *(uploaded reference images)*
| Field | Type | Notes |
|---|---|---|
| booking | FK → Booking, `CASCADE`, related_name='references' | |
| asset | FK → MediaAsset, `PROTECT` | |
| note | CharField(200, blank) | |
**Indexes:** `(booking)`. Max 8 rows enforced at form/service level.

### Appointment
| Field | Type | Notes |
|---|---|---|
| booking | OneToOne → Booking, `SET_NULL`, null, related_name='appointment' | |
| client | FK → Client, `PROTECT` | |
| start_at | DateTimeField, db_index | |
| end_at | DateTimeField | |
| status | CharField(20), choices | scheduled / confirmed / done / no_show / cancelled |
| calendar_event_id | CharField(200, blank) | Google Calendar hook — unused now |
| internal_notes | TextField(blank) | |
**Constraints:** `CHECK (end_at > start_at)`.
**Double-booking prevention (DB-level, not just app-level):**
```
EXCLUDE USING gist (
  tsrange(start_at, end_at, '[)') WITH &&
) WHERE (status IN ('scheduled','confirmed'))
```
This requires `btree_gist`. It is the one constraint that makes overlapping appointments
**impossible**, not merely unlikely. App-level checks give good errors; this gives correctness.
**Indexes:** `(start_at)`, `(status, start_at)`.

---

## 8. shop

### ProductCategory  *(name, slug, description, cover, order, is_featured)*
### Product
| Field | Type | Notes |
|---|---|---|
| name / slug | | |
| description | TextField | |
| category | FK → ProductCategory, `PROTECT` | |
| product_type | CharField(20), choices | print / poster / original / merch / digital |
| price | DecimalField(9,2) | |
| currency | CharField(3) | |
| stock | PositiveIntegerField(null) | null = made-to-order / unlimited |
| is_limited | BooleanField | |
| edition_size | PositiveSmallIntegerField(null) | |
| availability | CharField(20), choices | in_stock / made_to_order / sold_out / coming_soon |
| is_featured | BooleanField, db_index | |
| status | CharField(20), choices | draft / published / archived |
| tags | M2M → core.Tag, blank | |
**Constraints:** `CHECK (price >= 0)`, `CHECK (stock IS NULL OR stock >= 0)`.
**Indexes:** `(status, is_featured)`, `(category, status)`, `(slug)`.

### ProductImage  *(same shape as TattooImage)*

### Order / OrderItem  *(skeleton only — no payment provider)*
`Order(currency, subtotal, status ∈ {cart, pending, paid, shipped, cancelled, refunded},
email, created_at)` and `OrderItem(order, product FK PROTECT, unit_price, qty)`.
Present so the data model is stable when Stripe lands; **no views, no checkout, no provider**.
Price is **snapshotted** into `OrderItem.unit_price` — never read live from Product.

---

## 9. contact

### ContactMessage
| Field | Type | Notes |
|---|---|---|
| name / email / phone | | |
| subject | CharField(160, blank) | |
| message | TextField | |
| is_read | BooleanField, db_index | |
| replied_at | DateTimeField(null) | |
**Indexes:** `(is_read, -created_at)`.

---

## 10. core.Tag  *(shared across tattoos / artworks / products / clients)*
`name(60)`, `slug(70) unique db_index`, `kind(20)`.
**Constraint:** `UNIQUE(slug, kind)` so a tattoo tag and a product tag can differ.

---

## 11. concept (future AI hook — inert, no views)

### ConceptRequest
`client_email`, `subject`, `style FK SET_NULL`, `placement`, `size`, `mood`, `details`,
`status ∈ {requested, processing, ready, rejected}`, `result_asset FK MediaAsset SET_NULL`,
`disclaimer_shown` always true.
Shipped as schema only, so the future feature needs no migration on live data.
Results are **always** labelled CONCEPT ART and never presented as performed work.

---

## 12. Global conventions

- **Timestamps:** `created_at` auto_now_add, `updated_at` auto_now.
- **Publishing:** models with public pages use `status` + `published_at`, never
  `is_published` boolean alone, so scheduling is possible later.
- **SEO:** a `SEOMixin` (abstract) provides `meta_title`, `meta_description`,
  `og_image`, and a `get_meta_title()` fallback chain.
- **Slugs:** generated in `save()` only when empty — never overwrite an editor's custom slug,
  because changing a slug breaks indexed URLs.
- **Uploads:** renamed to UUID paths; originals preserved; derivatives in a sibling directory.
- **Delete policy summary:**
  `CASCADE` only where the child cannot exist without the parent (images of a tattoo,
  references of a booking). `PROTECT` everywhere history matters (client→booking,
  tattoo→image asset, artwork→category, order→product). `SET_NULL` for optional
  cross-links (gallery provenance, calendar id, style on booking).
