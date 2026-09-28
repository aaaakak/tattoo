# Art Direction — Gothic Fine-Line Engraving

Extension to the INK AS DATA design system. The five original screenshots remain the
**design** references (`reference/ref_*.png`); the images documented here are the
**art/tattoo** references (`reference/art-references/`). The two sets are deliberately kept
separate — see `reference/MANIFEST.json`.

Source: Telegram, 2026-09-24 11:48. Four images, hash-verified, measured below.

---

## The central finding

The gothic engraving references do not *extend* INK AS DATA so much as **close the loop**.

Measured, three of the four are true monochrome, and their dominant tone is `#F0F0F0` at
29–56% of pixels — **the exact paper value measured from design reference 4**. The tattoo
art references and the editorial design references share one paper ground and one ink
black. The identity was already correct; the artwork confirms it rather than contradicting it.

Consequence for the design system: **no new colour tokens are needed.** What the art
references add is a *treatment vocabulary* (see below), not a palette.

---

## Measured references

### 1. `gothic-angel-sword-paper.png` — 1246×1354 · MONOCHROME
`#F0F0F0` 29.1% · `#000000` 7.6% · paper 45.4% / ink 20.9%

Winged female figure beside an ornate vertical sword, thorny vines, heavy cross-hatching.
Fine-line with dense etching texture. Distressed antique paper ground with horizontal
scratches. **The single strongest reference for the tattoo portfolio direction** — it is
compositionally a large-format tattoo design and reads beautifully at both thumbnail and
full-bleed scale.

### 2. `tattoo-flash-angel-panel.png` — 880×1484 · MONOCHROME
`#F0F0F0` 17.4% · paper 52.1% / ink 5.4%

The densest reference: a tattoo-flash panel containing a dark-winged angel with sword, a
haloed figure, a hooded figure, crosses, a moth/eye motif, filigree and manuscript script.
Predominantly *paper* (52%) with fine ink linework rather than heavy black mass — this is
the reference that governs **detail density at small sizes**, and the argument for generous
whitespace around intricate pieces.

### 3. `triptych-angel-cross-seraph.png` — 1354×1552 · MONOCHROME
`#F0F0F0` 33.4% · paper 55.6% / ink 5.9%

Vertical triptych: angel in a gothic arch niche, an ornate cruciform spire with wings, a
winged seraph/knight with staff. Aged manuscript texture. This is the reference for
**symmetrical, panel-based composition** and for how a collection of pieces should be
presented side by side — directly relevant to the editorial run and gallery layout.

### 4. `sacred-heart-octagon-frame.png` — 1004×1182 · **CHROMATIC**
`#000000` 14.9% · ink 67.7% / paper 2.4% · channel spread 9 (deep crimson cast)

Anatomical heart pierced by a sword, octagonal Greek-key frame, baroque filigree.

**This is the outlier and it is recorded honestly rather than forced into blackwork.** It is
not monochrome: it carries a genuine deep-red cast and is 68% dark. Two consequences:

- It must **not** be placed in a blackwork-only filter, or the site lies about the work.
- It establishes that the artist's practice includes **dark-ground, chromatically-cast
  pieces** alongside paper-ground monochrome ones.

This is exactly why the tattoo model has `is_color` as a real field with three states
(colour / black & grey / undecided) rather than a boolean. The schema already anticipated
this. The art simply proves it was necessary.

---

## Treatment vocabulary — what the art references add

These are **image-treatment rules**, and they are what Phase 2 implements.

| Device | Rule | Source |
|---|---|---|
| **Detail floor** | Intricate engraving must never render below 400px wide. Fine linework below that destroys into noise. Thumbnails use the dither variant precisely because it degrades deliberately instead of accidentally. | ref 2 (5% ink) |
| **Paper breathing** | Fine-line pieces sit on generous whitespace. Reference 2 is 52% paper — density is a property of the *artwork*, not the layout. Cards get more padding, not less. | refs 2, 3 |
| **Dither threshold is per-image** | High-key paper-ground pieces (refs 1–3) need a low dither threshold to keep thin lines legible. Dark-ground pieces (ref 4) need a high one or they crush to solid cobalt. **Threshold is a per-asset field, not a global constant.** | ref 4 |
| **Aspect fidelity** | References range 0.59–0.92 ratio — tall, panel-like. Portrait is the default for tattoo work; the masonry must not force landscape crops onto vertical pieces. | all |
| **Symmetry honoured** | Centred, axial compositions (refs 3, 4, 5-design) must be presented centred, not forced into asymmetric offset runs. The staggered run is for *collections of pieces*, not for individual symmetrical designs. | refs 3, 4 |
| **Manuscript ground** | Faint script texture is intrinsic to the artwork, not a site texture. It lives *inside* the image, so the site must not add a competing texture behind it. | refs 1, 2, 3 |
| **Ink-on-paper inversion** | On the dark ground, the engraving reads as paper-white linework on near-black — the same inversion design reference 3 performs. This is the natural dark-mode rendering and requires no special treatment. | design ref 3 |

---

## What this changes in the codebase

1. `inspectimages`-style **per-asset `dither_threshold`** and `detail_floor` fields on
   `MediaAsset` — carried in Phase 2's image pipeline.
2. `ArtworkImage` / `TattooImage` gain nothing new: the existing `is_color` on `Tattoo`
   already covers the chromatic case.
3. The `DitherImage` component was already correct — the art confirmed the design rather
   than challenging it. It gains a per-image threshold hook.
4. Documentation updated: `docs/visual-analysis.md` gains a cross-reference to this file.

## What is explicitly NOT copied

No individual artist's work, style signature, composition or branding is reproduced. The
sample content for development is **generated original artwork** in this direction, labelled
in the database as demonstration content, and never presented as real work by a real artist.
The references inform *technique and treatment* only.
