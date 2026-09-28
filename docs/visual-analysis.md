# Visual Analysis — Five Reference Screenshots

Source: `~/Downloads/Screenshot 2026-09-24 at 10.5*` (copied to `reference/`)
Verified by SHA-256 against the Telegram image cache — identical files.
Palette values below are **measured** via pixel quantisation, not estimated.

---

## Reference 1 — `ref_10-54-41.png` (3188 x 1982)

**Identity:** Nous Portal landing page (dark).

### Measured palette
| Hex | Share | Role |
|---|---|---|
| `#000020` | 68.1% | Ground — near-black, faint blue cast |
| `#000030` | 8.3% | Secondary ground |
| `#101040` | 3.3% | Hairline / border |
| `#202050` | 1.9% | Muted text |
| cobalt | 0.1% | Accent only (buttons) |

### Findings
- **Ground is near-black with a cold cast**, not navy-blue. Blue is decoration on top of black.
- **Accent blue is vanishingly rare — 0.1% of pixels.** This is the single most important
  discipline to transfer: the accent earns attention precisely because it is almost absent.
- **Typography:** ultra-condensed display headline ("Everything to Power Hermes Agent"),
  title case, extremely tight tracking, ~96px equivalent. Body in neutral neo-grotesk.
  Monospace for technical labels (`// OVERVIEW`, `#1`, `#2`), all-caps, tracked +15-20%.
- **Image treatment:** classical bust rendered as **1-bit dither/halftone**, pale ice-blue
  highlights on near-black shadows. Juxtaposed with a **pixelated retro OK/Cancel dialog box**.
  The "cyber-classical" collision is the concept.
- **Layout:** asymmetric staggered grid. Feature #1 text-above-image (left), Feature #2
  image-above-text (offset right), Feature #3 left again. The eye zigzags.
- **Corners:** 0px radius throughout. **Borders:** 1px hairlines (`#101435`-class).
- **Buttons:** solid cobalt primary CTA, no border, uppercase white text.

### Transferable
Accent scarcity (0.1% discipline) · dither/1-bit image treatment · staggered asymmetric grid ·
0px radius brutalism · mono `#N` technical labels · classical-artwork-meets-digital-UI tension.

### Do NOT copy
Nous branding, the terminal card, the credit-balance sidebar, the specific OK/Cancel motif.

---

## Reference 2 — `ref_10-54-46.png` (3186 x 2000)

**Identity:** Nous Portal dashboard.

### Measured palette
| Hex | Share | Role |
|---|---|---|
| `#000020` / `#000030` | 54.8% | Ground + panels |
| `#F0F0F0` | 13.2% | Primary text |
| `#101040` | 5.6% | Sidebar / hairline |
| `#0000E0` (cobalt) | 3.1% | Active CTA |
| `#202040` | 3.0% | Dividers |

### Findings
- Off-white text (`#F0F0F0`, NOT pure white) at 13% — off-white is the *foreground* here,
  and it is the same off-white family as the tattoo-relevant paper ground in Ref 5.
- **Halftone/dither eye artwork** rendered in ice-blue on near-black, used as a cinematic
  wide section divider (~21:9 crop).
- Sidebar: dense 8px-grid vertical stack, small icons + text, active state = white text +
  subtle background lift.
- Cards: 24px padding, 20-24px gaps, 1px subtle borders, 4px radius (slight softening vs Ref 1).
- **Terminal card** implies a typing animation; chat card implies scroll/push.

### Transferable
Off-white-not-white discipline · wide cinematic halftone section dividers · the idea of a
persistent structural sidebar drawn in hairlines · status metadata in mono.

### Do NOT copy
Billing UI, credit balances, the specific dashboard chrome, the eye motif.

---

## Reference 3 — `ref_10-54-51.png` (3224 x 1990)

**Identity:** Hermes Agent marketing landing.

### Measured palette
| Hex | Share | Role |
|---|---|---|
| `#0000E0` cobalt | 38.7% | Full-bleed field |
| `#0000B0` | 21.9% | Pillar-box margin blue |
| `#2020E0` → `#5050E0` | 15.7% | Elevated / hover states |

### Findings
- **85.5% of pixels are cobalt** — this is the inverse of Ref 1. **This is the anti-pattern
  for TattoWeb.** The brief explicitly forbids the site being predominantly blue.
  Ref 3 is studied for *technique*, then deliberately inverted.
- **Technique worth taking:** white classical engraving as **pure line art, duotone, no
  gradients** — shading carried entirely by hatched/cross-hatched strokes that scale cleanly.
- **Technique worth taking:** the artwork is contained in a square frame, but its radiating
  lines **break out of the frame**, creating tension. Reusable for tattoo hero composition.
- Century Schoolbook-class optical sizing (body text visibly heavier than display text).
- Pillar-box framing: a deeper blue vertical margin frames a central content column.

### Transferable
Engraving-as-line-art duotone (the most tattoo-native device in the whole set) ·
**frame-breakout composition** · pillar-box framing · white-on-dark CTA contrast hierarchy.

### Do NOT copy
Cobalt as a background field. This directly violates the brief. Inverted on purpose.

---

## Reference 4 — `ref_10-54-56.png` (2892 x 2028)

**Identity:** Hermes feature page — **the most transferable reference.**

### Measured palette
| Hex | Share | Role |
|---|---|---|
| `#F0F0F0` paper | 50.2% | Off-white ground |
| `#0000B0` deep blue | 13.1% | Vertical pillar bars, borders |
| `#3030F0` → `#6060F0` | ~12% | Dithered illustration midtones |
| `#E0E0F0` | 3.6% | Illustration highlights |

### Findings
- **Off-white paper ground (#F0F0F0) at 50%** — a genuinely light page in this reference set.
  This is the paper tone to inherit.
- **Thick solid blue vertical bars flank the content**, compressing it inward — a printed
  editorial / book-page framing device. Highly reusable and distinctive.
- **Strict 3-column editorial grid.** Each column: cropped landscape image → small mono
  label (`#4 DELEGATE`) → condensed display title → grotesk body → large square artwork.
  Vertical alignment is exact across all three columns.
- **Display font here is an ultra-condensed high-contrast SERIF** ("Tasks Multiplied",
  "Browse the Web") — a critical nuance. The system is not sans-only.
- **Images are monochromatic cobalt duotone + dither/halftone**, giving a risograph /
  woodcut / printed texture. Classical subjects (knight in armour, falling figure, staircase
  to a sun). One image carries a subtle thin rainbow-gradient border — the only chromatic
  gradient anywhere in the five references.
- Thin horizontal rules separate header / grid / FAQ. Minimal `+` accordion affordance.

### Transferable
Off-white paper ground · **flanking vertical bars** · strict 3-column editorial grid with
fixed internal column order · mono `#N LABEL` + condensed display title pairing ·
cobalt-duotone dithered imagery · thin horizontal section rules · minimal accordion (+).

### Do NOT copy
Hermes copy, the `#4 DELEGATE` labels verbatim, the knight/staircase subject matter, the
rainbow-gradient border.

---

## Reference 5 — `ref_10-55-01.png` (1270 x 2026, PORTRAIT)

**Identity:** A single gothic fine-line ink illustration. **Not a UI. Not a website.**
**Zero cobalt — measured pure greyscale.**

### Measured palette
| Hex | Share |
|---|---|
| `#A0A0A0` / `#B0B0B0` | 17.0% |
| `#909090` | 6.6% |
| `#707070` / `#606060` | 13.3% |
| `#505050` / `#404040` / `#303030` | 28.0% |
| cobalt | **0.0%** |

### Findings
- **This is the emotional centre of the project.** A tattoo-adjacent artwork: ink, paper,
  cross-hatching. It is the only reference that is *not* software branding, and it is the
  one that tells us what a tattoo artist's world should feel like.
- **Subject:** gothic figure, thorny/flame-like wings, ornate vertical sword, floating
  thorny cross, baroque filigree, hanging chain with beaded pendulums, thorned brambles.
- **Technique:** fine-line ink, shading by **hatching and cross-hatching only** — no smooth
  gradients. Quality of an etching or engraved plate.
- **Background texture:** faint handwritten cursive script (archaic French — "présente",
  "écrivois", "étoit"), used as pure texture. A grimoire / old-correspondence atmosphere.
- **Asymmetry within symmetry:** centred axis, but the left wing sweeps higher, the sword
  anchors left, filigree densifies bottom-right. Balanced, never mirror-perfect.
- **Natural layering for parallax:** foreground (sword, filigree) → midground (figure) →
  midground-2 (wings, cross) → background (script texture). Four separable depths.
- Slight vignette darkening at the outer edges.

### Transferable — the highest-value set
Black ink on off-white paper · **cross-hatching as the shading language** · script/manuscript
as background texture · four-layer depth for parallax · gothic ornament as framing device ·
asymmetry-within-symmetry · vignette.

### Do NOT copy
The specific figure, the manga-adjacent character design, the anime styling. The *technique*
transfers; the *character* does not.

---

## Synthesis — what the references collectively say

Three distinct ground systems appear across the five:

1. **Near-black cold ground** (Refs 1, 2) — 68% and 55% share
2. **Off-white paper ground** (Refs 4, 5) — 50% and greyscale
3. **Full cobalt field** (Ref 3) — the anti-pattern

The brief demands black/near-black as primary with off-white typography and cobalt as accent.
That maps cleanly onto **Refs 1 + 2 as the dark mode** and **Refs 4 + 5 as the light/paper
mode** — with Ref 3's cobalt field explicitly rejected as a background and retained only as
the accent *ink*.

### The five devices that define the identity

1. **Halftone / 1-bit dither image treatment** (Refs 1, 2, 4) — the signature. Applied to
   tattoo photography: dithered cobalt-on-black as the default state, resolving to full
   fidelity on interaction.
2. **Ultra-condensed oversized display type** (Refs 1, 3, 4) — including the nuance that
   Ref 4 uses a condensed *serif*. The system is display-condensed + grotesk body + mono meta,
   with an optional condensed serif voice for editorial section titles.
3. **Monospace technical metadata** (Refs 1, 2, 4) — `// 003 — PLACEMENT: FOREARM`,
   tracked +15-20%, all-caps, always small.
4. **Editorial asymmetry** — Ref 1's staggered zigzag, Ref 4's strict three-column with
   fixed internal order, Ref 3's frame-breakout, Ref 5's asymmetry-within-symmetry.
5. **Hairline + 0px radius brutalism** (Ref 1) softened to near-zero where the paper mode
   is active (Refs 2, 4 use 4px).

### The collision that makes it original
Refs 1, 2 and 4 all stage a deliberate **collision between classical artwork and digital UI**
— engraving over dithered pixels, marble busts with retro dialogs. For a tattoo artist this
translates exactly: **the artwork is the classical layer; the halftone, mono metadata and
hairline grid are the digital layer.** Tattooing has always been ink on skin; here it becomes
ink as data. That tension is the identity, and it is original to this artist.

---

## Cross-reference: art direction

This document analyses the five **design** references (the INK AS DATA source screenshots).

A second, separate set of **art/tattoo** references (gothic fine-line engraving) was received
later and is documented in `docs/art-direction.md`, with the files under
`reference/art-references/`. The two sets are deliberately kept distinct and are catalogued
in `reference/MANIFEST.json`.

The key finding of that second analysis: the art references share the *same* paper tone
(`#F0F0F0`) and ink black as design reference 4, so they extend the existing system's
treatment vocabulary rather than changing its palette.
