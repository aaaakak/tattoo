# Components — TattoWeb

Component names map to template files under `templates/components/` and CSS classes under
`static/css/components.css`. Every component is listed with its **contract** (inputs), its
**states**, and the reference it derives from.

Convention: `{% include "components/x.html" with ... only %}` — always `only`, so a component
can never accidentally depend on the caller's context. Dependencies must be explicit.

---

## A. Structure

### `base.html`
The single document shell: `<!doctype html>`, `<html lang>` from `SiteSettings`, head partial,
grain overlay, header, `{% block content %}`, footer, page-transition overlay, script tag.
Blocks: `title`, `meta`, `content`, `body_class`, `extra_css`, `extra_js`.
Body class carries `page--<name>` and `theme--ink|paper` so page-level CSS is scoped, never global.

### `SiteHeader`
- **Contract:** `nav_items` (from a context processor), `artist`, `cta_open` (booking switch).
- **Anatomy:** monogram/wordmark left · mono nav centre or right · one cobalt CTA · hairline bottom.
- **States:** transparent over hero → glass (blur + `rgba(5,5,7,.72)`) after 80px scroll.
- **Interaction:** nav items are mono, tracked, `--ink-mute` → `--ink-white` on hover with a
  1px cobalt underline that grows from left (180ms). Active item is `--ink-white` with a
  persistent cobalt hairline.
- **Mobile:** full-screen overlay menu, mono oversized items, staggered 40ms reveal, body
  scroll locked, `Esc` closes, focus trapped.
- **From:** Ref 4's centred header + mono nav; Ref 1's hairline chrome.

### `SiteFooter`
- **Anatomy:** artist name (display, large) · mono contact block · social links · working hours ·
  a `// END OF DOCUMENT` mono marker.
- **From:** Ref 1's mono utility layer.

### `PillarFrame`
- **Contract:** `side` (left|right|both), `width`.
- **Purpose:** solid `--c-cobalt-deep` vertical bars flanking a section (Ref 4).
- **Discipline:** max 2 per page. Collapses to a 3px top rule under 768px.

### `SectionMarker`
- **Contract:** `index` (int), `label` (str).
- **Renders:** `// 003 — PLACEMENT: FOREARM` in mono, `--cobalt-hi` for the index, `--ink-mute`
  for the label, with a 1px hairline occupying the remaining width.
- **From:** Ref 1's `#N` labels, Ref 4's `#4 DELEGATE`.

### `HairlineRule` · `GrainOverlay`
1px `--c-hairline` rule with optional mono caption. Grain is a single fixed SVG
`feTurbulence` layer, `pointer-events:none`, opacity 0.035 (ink) / 0.025 (paper), mounted
**once** in `base.html` — never per-component.

---

## B. Typography

| Component | Contract | Notes |
|---|---|---|
| `DisplayStatement` | `lines: list[str]`, `size` | Ultra-condensed all-caps. May overlap imagery and break its frame (Ref 3). Each line is a mask wrapper for staggered reveal. |
| `EditorialTitle` | `text`, `level` | High-contrast condensed **serif** (Ref 4). Used for section titles only. |
| `MonoMeta` | `text`, `prefix` | The `// 003 — LABEL` pattern. Always 11px, tracked, all-caps. |
| `MetaList` | `pairs: list[(k, v)]` | Definition-list of mono keys + value. Used for tattoo specs. Keys `--ink-dim`, values `--ink-white`. |
| `BodyProse` | `html` | Max 68ch measure, 17px, leading 1.65. Wraps `|safe` content from the CMS. |
| `StatBlock` | `value`, `label` | Oversized display numeral + mono label. The 10+ / 1200+ / 08 / 01 row. Counts up on first intersection (600ms), respects reduced motion. |

---

## C. Image — the signature layer

### `DitherImage`  ← **the core component of the entire site**
- **Contract:** `asset`, `alt`, `sizes`, `ratio` (intrinsic W/H), `mode`
  (`ink` | `paper`), `priority` (bool), `resolve_on` (`hover` | `view` | `always`).
- **Anatomy:** a `<picture>` with the full-fidelity source, overlaid by a second `<img>`
  carrying the pre-generated dither sibling, `aria-hidden="true"`.
- **States:**
  - Rest: dither layer opacity 1, full layer opacity 0 (grid thumbnails).
  - Resolved: full layer opacity 1 over 420ms (`--dur-base`, `--ease-out`).
  - Or reversed, depending on `mode` — paper mode rests on full and dithers on hover.
- **No-JS:** full-fidelity image is the `<img>` in the `<noscript>` path and is also the
  layered element; with JS off, everything renders resolved. The dither is pure enhancement.
- **Reduced motion:** transition duration 0; resolves immediately.
- **Performance:** both variants are pre-generated at upload. **Zero runtime CPU.** The
  component therefore costs one extra HTTP request that is almost always cache-warm.
- **Fallback:** if a dither derivative is missing, the component renders the full image and a
  `data-dither-missing` attribute — it never shows a broken image, and the gap is visible in QA.

### `HeroCanvas`
- **Contract:** `asset`, `kicker`, `title_lines`, `ctas`.
- **Anatomy:** full-viewport. Image layer (parallax, max 1 layer) → display statement
  overlapping the image → mono metadata rail → two CTAs.
- **Composition:** the display type is permitted to **break the frame** of the image
  container (Ref 3's engraving breakout) — the single most distinctive hero device available.
- **Motion:** image parallax `translate3d(0, scrollY * 0.15, 0)`, rAF-throttled, transform-only;
  text reveal per line with 60ms stagger; grain and a slow cobalt light sweep (60s, opacity
  0.04) — the only ambient motion on the site.
- **Mobile:** no parallax (disabled under 768px and on `prefers-reduced-motion`), title scales
  to `--fs-display-m`, CTAs stack full-width.

### `ArtworkCard`
- **Contract:** `obj`, `kind` (`tattoo|artwork|product`), `span`.
- **Anatomy:** `DitherImage` · mono index + category · title · MetaList (placement/medium) ·
  1px hairline.
- **Hover:** dither resolves (420ms) · cobalt hairline draws across the top (180ms) ·
  mono metadata block slides up 8px and fades in · image scales to 1.02 (not more —
  restraint). `focus-visible` produces the identical state for keyboard users.

### `Lightbox`
- **Contract:** `items` (from the gallery), `start_index`.
- **Features:** fullscreen, backdrop `rgba(5,5,7,.96)`, image centred with mono metadata rail
  beneath, previous/next, close, counter `03 / 24`.
- **Keyboard:** `←` `→` `Esc` `Home` `End`. **Touch:** horizontal swipe. **Focus:** trapped,
  returns to the originating card on close. `role="dialog" aria-modal="true"`.
- **Loading:** preloads ±1 image, uses the `_1600` derivative, shows the LQIP blur while loading.
- **Deliberately not:** no zoom-and-pan, no pinch-zoom implementation. Native browser zoom
  handles that better than a hand-rolled canvas.

### `MasonryRun`
- **Contract:** `images`, `columns` (responsive map).
- **Implementation:** CSS multi-column with `break-inside: avoid` and **explicit intrinsic
  aspect ratios on every image** so nothing reflows. No JS layout library, no absolute
  positioning — this is what keeps it fast and CLS-free. `span` from `GalleryImage` allows a
  deliberate wide item for asymmetry.

---

## D. Layout runs

### `EditorialRun`  (from Ref 4)
- **Contract:** `items`, `columns=3`.
- **Fixed internal column order (non-negotiable, this is the Ref 4 signature):**
  cropped landscape image → mono label → editorial serif title → body → large square artwork.
- Alignment of the text blocks across columns is exact — achieved with a subgrid, not with
  padding hacks.

### `StaggeredRun`  (from Ref 1)
- **Contract:** `items`.
- **Behaviour:** alternates text-above-image / image-above-text, offset on the horizontal
  axis so the eye zigzags. Two-column on desktop, single column on mobile with the stagger
  removed (a stagger that cannot be perceived is just misalignment).

### `FilterRail`
- **Contract:** `options`, `active`, `param_name`.
- Mono chips, 1px hairline, 0 radius. Active chip: cobalt border + `--ink-white` text.
  Chips are real `<a href>` links with query params — filters work without JS and every
  filtered view is shareable and indexable. JS only enhances with `fetch()` + `pushState`.
- Live region announces the result count for screen readers.

### `SpecTable` · `AccordionItem` · `StatRow`
`SpecTable` = `MetaList` in a bordered grid for tattoo detail pages (placement, size,
duration, price, session date). `AccordionItem` = the minimal `+` affordance from Ref 4's
FAQ, used for artist notes and shop shipping info. `StatRow` = the `StatBlock` row on About.

---

## E. Forms

### `FieldGroup`
- **Contract:** `field`, `label`, `help`, `required`.
- Mono label above, 1px hairline input, 0 radius, cobalt focus ring (2px, offset 1px),
  inline error in a red-tinted mono line beneath. `aria-describedby` wired to help + error.

### `FileDropZone`
- **Contract:** `field`, `max_files=8`, `max_mb`.
- Drag-and-drop with click fallback, thumbnail grid with per-file remove, live validation of
  type and size client-side, and a server-side re-validation that is the only one that
  actually counts. Progress per file. Rejects SVG and non-images with a specific message.
- Must degrade: a plain `<input type="file" multiple>` is always present in the DOM and is the
  functional path with JS off.

### `StatusPill`
- **Contract:** `status`.
- Mono uppercase, 1px border, colour-mapped across the 8 booking statuses. Read-only in the
  admin list; not a form control.

### `AvailabilityCalendar`
- **Contract:** `open_days`, `closed_days`, `month`.
- Month grid, mono numerals, available days are `--ink-white` with a cobalt dot, closed days
  are `--ink-dim` and `aria-disabled`. Data comes from `/api/v1/availability/days`. Keyboard
  navigable as a grid (`role="grid"`). Never a picker library — a hand-built grid is ~80 lines
  and avoids a dependency.

---

## F. Explicitly excluded components

Cookie-banner SaaS modals · testimonial carousels · "trusted by" logo bars · newsletter
popups · chat widgets · animated counters on every section (counts appear **once**, on About) ·
social share button clusters · breadcrumbs (the site is two levels deep; breadcrumbs would be
noise) · pagination with page numbers in the gallery (infinite scroll with a "load more"
button and full keyboard access instead).
