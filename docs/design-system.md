# Design System — TattoWeb

Derived from the measured analysis in `visual-analysis.md`.
Name of the identity: **INK AS DATA** — black ink and paper craft rendered through a
digital interface layer (halftone, mono metadata, hairline grid).

Values marked *(measured)* come from pixel quantisation of the five references.

---

## 1. Colour

### Dark mode (primary — "INK")
| Token | Hex | Source | Use |
|---|---|---|---|
| `--c-void` | `#050507` | *(measured base, shifted off pure* `#000020` *to remove the software blue cast)* | Primary ground |
| `--c-void-2` | `#0B0B0E` | derived | Elevated surface |
| `--c-hairline` | `#1C1C22` | Ref 1 `#101040` desaturated | 1px borders, grid lines |
| `--c-ink-white` | `#EDEAE4` | Ref 2 `#F0F0F0` warmed | Primary text |
| `--c-ink-mute` | `#8A8A93` | Ref 1 `#202050`-family, lifted | Secondary text |
| `--c-ink-dim` | `#4A4A52` | derived | Tertiary / disabled |

### Paper mode (secondary — "PAPER")
| Token | Hex | Source | Use |
|---|---|---|---|
| `--c-paper` | `#F0EFEA` | *(measured)* Ref 4 `#F0F0F0` warmed to aged-paper | Light ground |
| `--c-paper-2` | `#E4E2DA` | Ref 5 paper family | Card / inset |
| `--c-paper-ink` | `#0A0A0C` | Ref 5 ink | Text on paper |

### Accent — COBALT (rationed)
| Token | Hex | Source | Use |
|---|---|---|---|
| `--c-cobalt` | `#1B2CFF` | Ref 4 `#3030F0` / Ref 2 `#1110E3` | Active state, one CTA per viewport |
| `--c-cobalt-deep` | `#0000B0` | *(measured)* Ref 4 pillar bars | Flanking bars, borders |
| `--c-cobalt-hi` | `#6060F0` | *(measured)* Ref 4 dither midtone | Halftone highlight tint |

### Accent discipline rule (hard constraint)
Ref 1 measures cobalt at **0.1% of pixels**. Ref 3 measures it at **85.5%** and is the
declared anti-pattern. Therefore:

> **Cobalt may never exceed 5% of any viewport's pixels.**
> Permitted: active nav state, one primary CTA, 1px hover hairline, mono prefix glyph,
> halftone highlight tint, focus ring.
> Forbidden: page background field, large gradient fills, decorative blocks, body text.

### Contrast targets
- `--c-ink-white` on `--c-void` = 16.4:1 ✓ AAA
- `--c-ink-mute` on `--c-void` = 5.1:1 ✓ AA (body), use `--c-ink-white` for <16px prose
- `--c-cobalt` on `--c-void` = 3.2:1 — **large text / UI borders only, never small body copy**
- `--c-paper-ink` on `--c-paper` = 18.9:1 ✓ AAA

---

## 2. Typography

### Three voices (plus one editorial serif)

| Role | Stack | Notes |
|---|---|---|
| **Display** | `Anton`, `Archivo Narrow` 700, `Oswald` 700 | Ultra-condensed, all-caps, tracking `-0.04em`, `clamp(3rem, 11vw, 13rem)`, leading `0.86` |
| **Editorial serif** | `Playfair Display` 900 / `Bodoni Moda` 900 | Condensed high-contrast serif — the Ref 4 "Tasks Multiplied" voice, for section titles |
| **Body / UI** | `Inter`, `-apple-system`, sans-serif | 400/500; 16-18px; leading `1.65`; tracking `0` |
| **Mono** | `JetBrains Mono`, `SFMono-Regular`, monospace | 11-12px, all-caps, tracking `+0.16em`, for ALL technical metadata |

### Scale
```
--fs-display-xl : clamp(3rem, 11vw, 13rem)   /* hero statement */
--fs-display-l  : clamp(2.25rem, 6vw, 5.5rem)
--fs-display-m  : clamp(1.75rem, 3.5vw, 3rem)
--fs-title      : clamp(1.5rem, 2.4vw, 2.25rem)  /* editorial serif */
--fs-body       : 1.0625rem  (17px)
--fs-small      : 0.875rem
--fs-meta       : 0.6875rem  (11px)  /* mono */
```

### Rules
- Display type may **overlap imagery** and **break out of its frame** (Ref 3).
- Mono metadata always pairs a structural prefix: `// 003 — PLACEMENT: FOREARM`.
- Never set mono in sentence case. Never track display type positively.
- Maximum two type voices per viewport region.

---

## 3. Space & Grid

```
--space-unit : 8px      /* strict 8px base (Ref 1 finding) */
--gutter     : clamp(1rem, 4vw, 4rem)
--section-y  : clamp(5rem, 12vh, 12rem)
--max-w      : 1440px
--col-gap    : 24px     /* Ref 1 measured */
```

- **12-column** base grid, max-width 1440px.
- **Editorial three-column** sub-grid for feature runs (Ref 4), with a **fixed internal order**:
  image → mono label → display/serif title → body → large artwork.
- **Asymmetric staggered** layout for portfolio runs (Ref 1 zigzag).
- **Pillar bars:** optional 1px-to-8vw solid `--c-cobalt-deep` vertical bars flanking a
  section (Ref 4). Used sparingly, max twice per page.
- Mobile is **rethought, not shrunk** — the three-column editorial run becomes a single
  column with mono labels acting as section markers; pillar bars drop to a 3px top rule.

---

## 4. Form & Surface

- **Radius: 0px** default (Ref 1). Permitted `2px` on inputs only.
- **Borders:** 1px `--c-hairline` everywhere. 1px `--c-cobalt` on hover/active.
- **No shadows.** Depth comes from ground-value shifts and hairlines only.
- **Glass:** limited to one surface type — the sticky header and the lightbox chrome.
  `backdrop-filter: blur(12px) saturate(140%)`, ground `rgba(5,5,7,0.72)`, 1px hairline bottom.
  Used in exactly two places; not a general decoration.
- **Grain:** one global film-grain overlay, fixed, `pointer-events:none`, SVG feTurbulence,
  opacity 0.035 dark / 0.025 paper. GPU-cheap, applied once — never per component.

---

## 5. Image treatment — the signature

Two states, and the transition between them is the personality of the site.

**State A — FULL.** The artwork at full fidelity, duotone-mapped (`--c-void` → `--c-ink-white`,
or cobalt-duotone in paper mode). Slight desaturation, contrast lift, film grain.

**State B — DITHER.** Halftone / 1-bit ordered-dither (Bayer 4x4 or 8x8) of the same image,
rendered in `--c-cobalt-hi` on `--c-void`. This is the resting state for grid thumbnails.

### Transition
On hover/focus and on scroll-into-hero, State B **resolves** into State A over **420ms**
`cubic-bezier(.2,.7,.2,1)`.

### Implementation strategy (performance-first, in priority order)
1. **Preferred:** two pre-generated variants per image, produced at ingest by a Django
   `post_save` pipeline using Pillow — a WebP full-fidelity and a WebP 1-bit-dithered
   sibling. Cross-fade between two stacked `<img>` elements. Zero runtime CPU cost,
   works with no JS, degrades to State A if JS is off.
2. **Fallback for large hero only:** CSS `filter: url(#dither)` SVG filter — used on a single
   hero element, never on a grid of many images.
3. **Never:** per-frame canvas dithering at runtime.

Accessibility: the dither variant is `aria-hidden="true"`, decorative. The full-fidelity
image always carries the real `alt`. `prefers-reduced-motion: reduce` disables the transition
and renders State A immediately.

---

## 6. Motion

Motion is rationed like cobalt. Duration tokens:
```
--dur-fast  : 180ms
--dur-base  : 420ms     /* image resolve */
--dur-slow  : 720ms
--ease-out  : cubic-bezier(.2,.7,.2,1)
--ease-inout: cubic-bezier(.65,0,.35,1)
```

### Approved behaviours
| Behaviour | Implementation | Budget |
|---|---|---|
| Text reveal (display only) | per-line mask + `translateY`, IO-triggered, stagger 60ms | hero + section titles only |
| Image resolve (B→A) | opacity cross-fade of two stacked imgs | every dither surface |
| Image reveal on scroll | `clip-path` inset wipe, IO-triggered once | portfolio items |
| Parallax | `transform: translate3d` on max 2 layers, `rAF`-throttled | hero only |
| Hover metadata | mono label slides up 8px + cobalt hairline | portfolio items |
| Page transition | cobalt wipe overlay, 300ms out / 300ms in | full navigations only |
| Cursor | custom 8px cobalt ring, lags 80ms, `pointer: fine` only | desktop only |

### Hard limits
- ≤2 parallax layers site-wide, hero only.
- No WebGL. No particle systems. No constant ambient motion.
- All IO observers `unobserve()` after first fire.
- Everything collapses under `prefers-reduced-motion`.
- Every animation runs on `transform`/`opacity` only — never `width`/`top`/`filter` in a loop.

---

## 7. Component inventory (visual contract)

**Structure** — `SiteHeader` (sticky, glass, mono nav), `SiteFooter`, `PillarFrame`,
`SectionMarker` (mono `#NNN — TITLE`), `HairlineRule`, `GrainOverlay`.

**Type** — `DisplayStatement`, `EditorialTitle` (serif), `MonoMeta`, `MetaList`
(key/value pairs in mono), `BodyProse`.

**Image** — `DitherImage` (A/B states — the core component), `ArtworkCard`,
`HeroCanvas` (frame-breakout display + image), `Lightbox`, `MasonryRun`.

**Interaction** — `EditorialRun` (3-col fixed order), `StaggeredRun` (zigzag),
`FilterRail` (mono chips), `SpecTable`, `StatBlock` (10+ / 1200+ / 08 / 01),
`AccordionItem` (+ affordance from Ref 4), `PrimaryCTA`, `GhostCTA`, `CopyField`.

**Form** — `FieldGroup`, `FileDropZone` (multi reference upload), `StatusPill`
(booking status, mono), `AvailabilityCalendar`.

---

## 8. Explicitly rejected

Cobalt background fields · rainbow gradients · generic tattoo-shop templates · crypto/gaming
aesthetics · heavy neon glow · particle systems · WebGL · rounded-card SaaS layouts ·
drop shadows · glassmorphism beyond the two permitted surfaces · pure-white `#FFFFFF` text
(off-white only) · pure-black `#000000` ground (near-black only) · any Nous/Hermes copy,
logo, or motif.
