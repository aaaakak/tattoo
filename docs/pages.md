# Page Hierarchy — TattoWeb

Every page, its purpose, its blocks, and its CMS sources. A page is only designed here if it
earns its existence — the site is a portfolio, not a content farm.

Notation: `→` = composed of. `[CMS]` = editable in admin. `[fixed]` = structural, not editable.

---

## Navigation (global)

```
[ monogram ]   [fixed, from ArtistProfile.monogram]

TATTOOS   ARTWORK   GALLERY   ABOUT   SHOP   [ BOOK ]   [fixed labels]
                                                  └ cobalt CTA, hidden if booking closed
```
Mono, tracked, all-caps. Active item carries a cobalt hairline. Mobile: full-screen overlay,
oversized mono items, staggered reveal. `SiteSettings.booking_open` and
`ArtistProfile.is_booking_open` both gate the BOOK CTA (both must be true).

---

## 1. HOME  `/`

The one page that must convince in a single viewport.

| Block | Composition | Source |
|---|---|---|
| **Hero** | Full viewport. Kicker · oversized display statement (`ART THAT MOVES WITH YOU`, line-broken) · image with 1-layer parallax and **frame-breakout** type · mono metadata rail · `[VIEW TATTOOS]` `[BOOK A SESSION]` | `SiteSettings.hero_*`, `ArtistProfile.role_line` [CMS] |
| **Statement** | `INK IS ONLY THE MEDIUM.` in editorial serif + 2-sentence excerpt + `[READ FULL BIOGRAPHY]` | `ArtistProfile.statement`, `.biography` [CMS] |
| **Stat row** | `10+ YEARS` · `1200+ TATTOOS` · `08 SIGNATURE STYLES` · `01 VISION` — count-up once | `Statistic` rows, ordered [CMS] |
| **Featured tattoos** | `EditorialRun`, 3 columns, fixed internal order | `Tattoo.is_featured` [CMS] |
| **Featured artwork** | `StaggeredRun`, 2 items, zigzag | `Artwork.is_featured` [CMS] |
| **Styles strip** | Mono-indexed style chips with counts, `01 / BLACKWORK` … | `TattooStyle` ordered [CMS] |
| **Availability line** | `// NEXT AVAILABLE — 12 OCT` from the availability service | computed [fixed] |
| **Closing CTA** | `PillarFrame` + booking prompt | `SiteSettings` [CMS] |

Zero hard-coded business content. Every block has a documented fallback if the CMS is empty.

---

## 2. TATTOOS  `/tattoos/`

| Block | Composition | Source |
|---|---|---|
| Header | `// PORTFOLIO` `SectionMarker` + count | [fixed] |
| Filter rail | Style · Placement · Colour — real links, shareable URLs | `TattooStyle`, placements [CMS] |
| Grid | `MasonryRun` of `ArtworkCard`, paginated (24), "load more" + a real paginated fallback | `Tattoo` published [CMS] |

Empty state is designed, not an afterthought: a mono line inviting a booking.

---

## 3. TATTOO DETAIL  `/tattoos/<slug>/`

| Block | Composition | Source |
|---|---|---|
| Hero | Full-bleed primary image, dither resting state, resolves on load | `TattooImage.is_primary` [CMS] |
| Title block | Display title · style names · `SpecTable` (placement, size, duration, colour, session date, price range) | `Tattoo` fields [CMS] |
| Description | `BodyProse` | `Tattoo.description` [CMS] |
| Image set | `Lightbox` over the remaining images (detail/healed/process/studio variants) | `TattooImage` ordered [CMS] |
| Artist notes | `AccordionItem` | `Tattoo.artist_notes` [CMS] |
| Related | Up to 4 in the same style | computed [fixed] |
| CTA | `[BOOK A SIMILAR PIECE]` prefilling the style | [fixed] |

`[CMS]` throughout — the artist publishes a piece without touching code.

---

## 4. STYLES  `/styles/` · `/styles/<slug>/`

Index: mono-numbered style list with cover, description and piece count.
Detail: the style's statement, plus its published works as an `EditorialRun`.
Purpose: SEO surface (`blackwork tattoo` is a real query) and a genuine artist's taxonomy.

---

## 5. ARTWORK  `/artworks/`

**Structurally parallel to TATTOOS, presentationally distinct** — a gallery object, not a
body-placement record. No placement, no size-on-body, no duration.

| Block | Composition | Source |
|---|---|---|
| Header | `// ARTWORK` + count | [fixed] |
| Filter rail | Category · Year · Availability · Medium | `ArtworkCategory` etc. [CMS] |
| Run | `EditorialRun` (3-col, fixed order) — denser and more editorial than the tattoo grid | `Artwork` published [CMS] |

## 6. ARTWORK DETAIL  `/artworks/<slug>/`

Frame-object presentation: image centred with generous whitespace, `MetaList` of
medium / dimensions / year / edition, availability `StatusPill`, price if available.
`Lightbox` for detail shots. Cross-links to related works. Sold works stay visible with a
`SOLD` pill and are excluded from shop CTAs (provenance matters to collectors).

## 7. ARTWORK CATEGORY  `/artworks/category/<slug>/`

Category statement + its works. Paintings · Drawings · Illustration · Digital · Prints ·
Experimental — all `ArtworkCategory` rows, never hard-coded.

---

## 8. GALLERY  `/gallery/`

The immersive surface. Deliberately **not** a grid dump.

| Block | Composition | Source |
|---|---|---|
| Entrance | A single full-viewport dither image that resolves on scroll — sets the tone | collection cover [CMS] |
| Collections | Mono-titled collection run | `GalleryCollection` [CMS] |
| Main masonry | `MasonryRun`, asymmetric via `span`, explicit ratios, lazy + LQIP | `GalleryImage` ordered [CMS] |
| Lightbox | Fullscreen, keyboard + touch, mono counter `03 / 24` | [fixed] |
| Filters | Collection · Featured — link-based | [CMS] |

## 9. GALLERY COLLECTION  `/gallery/<slug>/`

A curated set with its own statement and masonry. Collections may reference any provenance
(tattoo or artwork) — that is the point of the nullable one-to-one provenance fields.

---

## 10. ABOUT  `/about/`

An editorial page, not a form-letter biography.

| Block | Composition | Source |
|---|---|---|
| Opening | `DisplayStatement` — the artist's own words | `ArtistProfile.statement` [CMS] |
| Portrait | Full-bleed or large-format portrait, dither treatment | `ArtistProfile.portrait` [CMS] |
| Biography | `BodyProse`, long-form, multi-paragraph | `ArtistProfile.biography` [CMS] |
| Practice | Specialties and approach, editorial two-column | [CMS] |
| Stats | The same `StatRow` as home | `Statistic` [CMS] |
| Location | City, studio address, map embed (only if configured) | `ArtistProfile`, `SiteSettings` [CMS] |
| CTA | `[BOOK A SESSION]` | [fixed] |

---

## 11. BOOKING  `/booking/`

The most functional page; must stay beautiful and must work without JS.

| Block | Fields | Notes |
|---|---|---|
| Identity | Name · Email · Phone · Instagram · Telegram | email required |
| The piece | Style (select from `TattooStyle`) · Placement · Approx. size · Colour / Black & Grey / Undecided · Description | description required |
| References | Multi-file upload, up to 8, images only, size-capped | client-side + server-side validation |
| Timing | Preferred date (`AvailabilityCalendar`) · Preferred time (morning/afternoon/evening) · Budget min/max | date optional; calendar shows real open days |
| Consent | Contact consent (required for GDPR) · honeypot (hidden) · timing token | [fixed] |
| Submit | `[SEND REQUEST]`, cobalt, one per viewport | rate-limited |

## 12. BOOKING SUCCESS  `/booking/success/<reference>/`

Mono-heavy confirmation: the reference code in oversize mono, a plain summary of the request,
what happens next (review → contact → approve → schedule), and the artist's contact channels.
`noindex`. The reference is **not** enumerable and this page leaks no client data beyond the
reference the client already holds.

---

## 13. SHOP  `/shop/`

| Block | Composition | Source |
|---|---|---|
| Header | `// PRINTS & ORIGINALS` | [fixed] |
| Filters | Category · Type · Availability | [CMS] |
| Grid | `EditorialRun` of products: image, mono type label, name, price, availability `StatusPill` | `Product` published [CMS] |

Honesty rule: sold-out and made-to-order states are stated plainly. No fake urgency, no
"only 2 left!" theatre.

## 14. PRODUCT DETAIL  `/shop/<slug>/`

Image set + `Lightbox` · description · price · stock/edition statement · shipping accordion ·
medium/dimensions for originals · `[ENQUIRE TO PURCHASE]` (the honest CTA while checkout is not
configured) replacing `[ADD TO CART]` — no button that pretends to work.

---

## 15. CONTACT  `/contact/`

Editorial layout, not a generic form page.

`DisplayStatement` (`// SAY IT PLAINLY`) → contact channels as a large mono `MetaList`
(Instagram · Telegram · Email · Phone) → studio location and working hours pulled from
`Availability` → a short message form (`ContactMessage`) → map only if configured.

Working hours are **derived from `Availability`**, not typed twice, so the site can never
contradict the booking system.

---

## 16. Error pages

`404` — a mono `// 404 — NOT FOUND`, an oversized line of display type, and routes back into
the portfolio. `500` — same grammar, no stack trace ever. Both on-brand and both styled.

---

## 17. `/design-system/`  (staff-only, DEBUG-gated)

Not a marketing page — an internal verification surface. Renders every colour token, every
type style at every size, every component in every state, in both themes, at every breakpoint.
This page is why the visual system can be *verified* rather than *believed*.
