# URL Map — TattoWeb

Two URL trees: Django (HTML + admin + DRF) and FastAPI (public JSON).
Both are versioned at the API boundary. Slugs are the public identity of content —
stable, human-readable, indexable. Numeric IDs are never exposed in public URLs.

---

## Django — public HTML

| Method | URL | View | Name | Notes |
|---|---|---|---|---|
| GET | `/` | `pages.home` | `home` | hero, statement, featured runs |
| GET | `/tattoos/` | `tattoos:TattooListView` | `tattoos:list` | paginated, filter by style/placement |
| GET | `/tattoos/<slug>/` | `tattoos:TattooDetailView` | `tattoos:detail` | full project page |
| GET | `/styles/` | `tattoos:StyleListView` | `tattoos:styles` | the style index |
| GET | `/styles/<slug>/` | `tattoos:StyleDetailView` | `tattoos:style_detail` | style + its works |
| GET | `/artworks/` | `artworks:ArtworkListView` | `artworks:list` | filter by category/year/availability |
| GET | `/artworks/<slug>/` | `artworks:ArtworkDetailView` | `artworks:detail` | |
| GET | `/artworks/category/<slug>/` | `artworks:CategoryDetailView` | `artworks:category` | |
| GET | `/gallery/` | `gallery:GalleryView` | `gallery:index` | editorial masonry |
| GET | `/gallery/<slug>/` | `gallery:CollectionDetailView` | `gallery:collection` | |
| GET | `/about/` | `artists:AboutView` | `artists:about` | biography, statement, stats |
| GET | `/booking/` | `booking:BookingView` | `booking:create` | form (GET) |
| POST | `/booking/` | `booking:BookingView` | `booking:create` | server-side fallback submit |
| GET | `/booking/success/<reference>/` | `booking:BookingSuccessView` | `booking:success` | reference-code confirmation |
| GET | `/shop/` | `shop:ProductListView` | `shop:list` | |
| GET | `/shop/<slug>/` | `shop:ProductDetailView` | `shop:detail` | |
| GET | `/contact/` | `contact:ContactView` | `contact:index` | form (GET) |
| POST | `/contact/` | `contact:ContactView` | `contact:index` | server-side fallback submit |
| GET | `/concept/` | `core:ConceptRequestView` | `core:concept` | **future** — inert, returns "coming soon" until enabled |

## Django — accounts

| GET/POST | `/account/login/` | `accounts:login` |
| GET/POST | `/account/logout/` | `accounts:logout` |
| GET/POST | `/account/password/` | `accounts:password_change` |

## Django — admin

| `/admin/` | Django admin (the artist's CMS) |
| `/admin/login/` | |
| `/admin/doc/` | disabled in prod |

## Django — machine-readable & SEO

| GET | `/robots.txt` | `core.views.robots` | serves a template, references sitemap |
| GET | `/sitemap.xml` | `django.contrib.sitemaps` | index of section sitemaps |
| GET | `/sitemap-tattoos.xml` | Tattoo sitemap | |
| GET | `/sitemap-artworks.xml` | Artwork sitemap | |
| GET | `/sitemap-styles.xml` | Style sitemap | |
| GET | `/sitemap-shop.xml` | Product sitemap | |
| GET | `/sitemap-pages.xml` | Static pages sitemap | |
| GET | `/.well-known/security.txt` | static |
| GET | `/healthz/` | liveness for deployment |

## Django — DRF (authenticated / administrative JSON)

Mounted at `/api/django/v1/`. Deliberately **not** `/api/v1/` — that belongs to FastAPI.
Keeping the prefixes distinct makes the ownership boundary visible in every URL and
prevents a router collision from silently shadowing a public API route.

| GET | `/api/django/v1/bookings/` | artist-only, filtered list |
| GET | `/api/django/v1/bookings/<reference>/` | artist-only |
| PATCH | `/api/django/v1/bookings/<reference>/` | artist-only, status transitions |
| GET | `/api/django/v1/clients/` | artist-only |
| GET | `/api/django/v1/stats/` | dashboard aggregates |

`DEFAULT_PERMISSION_CLASSES = [IsAuthenticatedOrReadOnly]` with
`IsArtistUser` on every write view. Session auth for the admin UI; token auth for scripts.

---

## Django — media (dev only)

| GET | `/media/<path>` | served by `django.views.static.serve` when `DEBUG=True` |
In production, nginx/Caddy serves `/media/` and `/static/` directly; Django never touches them.

---

## FastAPI — public JSON API

Base: `/api/v1`. OpenAPI at `/api/v1/docs` (dev), `/api/v1/openapi.json`.
All list endpoints: cursor or page pagination (`?page=`, `?page_size=` capped at 100),
consistent envelope, explicit `select`-shaped Pydantic schemas (never raw ORM dumps).

### Content (read-only, cacheable)

| GET | `/api/v1/tattoos` | filters: `style`, `placement`, `is_color`, `featured`, `q`, `ordering` |
| GET | `/api/v1/tattoos/{slug}` |
| GET | `/api/v1/styles` |
| GET | `/api/v1/styles/{slug}` |
| GET | `/api/v1/artworks` | filters: `category`, `year`, `availability`, `medium`, `featured`, `q` |
| GET | `/api/v1/artworks/{slug}` |
| GET | `/api/v1/categories` |
| GET | `/api/v1/gallery` | filters: `collection`, `featured` |
| GET | `/api/v1/gallery/{slug}` |
| GET | `/api/v1/products` | filters: `category`, `product_type`, `availability`, `featured` |
| GET | `/api/v1/products/{slug}` |
| GET | `/api/v1/styles-index` | lightweight `{slug, name, count}` for filter chips |

### Search

| GET | `/api/v1/search?q=` | cross-entity: tattoos, artworks, products, styles. Returns typed groups with counts. |

### Booking & availability

| GET | `/api/v1/availability?from=&to=&style=` | computed slots; respects `Availability` + `BlockedDate` + booked `Appointment`s |
| GET | `/api/v1/availability/days?month=` | which dates are open — drives the calendar |
| POST | `/api/v1/bookings` | JSON submit; **rate-limited**; returns `{reference, status}` |
| GET | `/api/v1/bookings/{reference}` | **requires the reference code + email match** — never enumerable |

### Contact

| POST | `/api/v1/contact` | **rate-limited**; honeypot + timing check |
| GET | `/api/v1/site` | SiteSettings + SocialLinks + artist summary for the frontend |

### Images (service-layer endpoint)

| GET | `/api/v1/images/{sha256}?w=&fmt=&dither=1` | on-demand derivative/dither; long cache headers; whitelisted `w` values only |

### Health / meta

| GET | `/api/v1/healthz` | includes a DB `SELECT 1` |
| GET | `/api/v1/meta` | API version, build, schema contract status |
| POST | `/api/v1/concept` | **future AI hook** — returns 501 until enabled; never presents output as real work |

---

## Routing rules

1. **Slugs, never IDs, in public URLs.** A tattoo lives at `/tattoos/raven-forearm/`,
   forever. Slug changes are the artist's explicit choice and 301-redirect via a
   `SlugHistory`-style redirect table in `core`.
2. **Trailing slashes** on all Django HTML routes (`APPEND_SLASH=True`); none on FastAPI
   JSON routes. This is deliberate: browsers and crawlers expect HTML with slashes,
   API clients expect them without.
3. **Two API prefixes, one owner each:** `/api/v1` = FastAPI (public, cacheable),
   `/api/django/v1` = DRF (authenticated, administrative). A URL's prefix tells you
   which stack and which auth model applies.
4. **No verb-in-URL, no `.json` suffix.** Content negotiation is header-based.
5. **Filters are query parameters, always** — never path segments — so filter combinations
   do not explode the route table and every filtered view stays shareable and cacheable.
