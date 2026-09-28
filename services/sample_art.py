"""
Procedural placeholder artwork generator.

PURPOSE: give the development site realistic content so the UI can be judged at real
proportions. This is DEMONSTRATION CONTENT and is labelled as such in the database
(``is_placeholder=True`` plus a visible caption). It is never presented as real work by a
real artist, and it deliberately does not imitate any individual artist's portfolio.

WHAT THIS IS: original procedural ink-style compositions — linework, hatching, rosaces,
arches, filigree and panel rules — drawn with Pillow primitives. They share the *visual
language* of the art references (ink on paper, cross-hatching, symmetry, ornamental
frames) without reproducing any specific artwork.

WHAT THIS IS NOT: it is not a generative model, and it does not claim to be art. It exists
so that layout, aspect ratios, dither thresholds and the resolve transition can be tuned
against real images. Every generated file is trivially replaceable through the CMS.

Run:  manage.py generate_sample_art
"""

from __future__ import annotations

import io
import math
import random
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFilter

# Palette matches the measured references: ink #0A0A0C on paper #F0EFEA.
INK = (10, 10, 12)
PAPER = (240, 239, 234)
MID = (150, 148, 142)


@dataclass(frozen=True)
class Composition:
    """One generated piece of demonstration artwork."""

    slug: str
    title: str
    width: int
    height: int
    seed: int
    motif: str


# Aspect ratios are taken from the measured art references (0.59-0.92, portrait-dominant).
COMPOSITIONS: tuple[Composition, ...] = (
    Composition("gothic-angel-winged", "Winged Figure, Study I", 1240, 1550, 11, "angel"),
    Composition("ornamental-sword", "Ornamental Sword, Plate II", 1000, 1600, 22, "sword"),
    Composition("medieval-cross-panel", "Medieval Cross, Panel", 1100, 1500, 33, "cross"),
    Composition("dark-winged-figure", "Dark Winged Figure", 1200, 1500, 44, "dark"),
    Composition("gothic-cathedral", "Cathedral Frontispiece", 1180, 1560, 55, "cathedral"),
    Composition("sacred-geometry-filigree", "Sacred Geometry with Filigree", 1200, 1200, 66, "geometry"),
    Composition("occult-symbol-panel", "Occult Symbol, Diagram", 1050, 1500, 77, "occult"),
    Composition("large-backpiece", "Back Piece, Full Composition", 1400, 1750, 88, "backpiece"),
    Composition("thorned-rosace", "Thorned Rosace", 1150, 1450, 99, "rosace"),
    Composition("arch-niche-figure", "Figure in Arch Niche", 980, 1580, 111, "arch"),
    Composition("seraph-triptych", "Seraph Triptych", 1350, 1550, 122, "triptych"),
    Composition("crown-and-chains", "Crown and Chains", 1100, 1100, 133, "crown"),
)


# --------------------------------------------------------------------------------------
# Drawing primitives
# --------------------------------------------------------------------------------------
def _paper(w: int, h: int, rng: random.Random) -> Image.Image:
    """Aged paper ground with subtle fibre noise and a vignette."""
    img = Image.new("RGB", (w, h), PAPER)
    px = img.load()

    # Paper grain: fine per-pixel variation so the dither has tone to work with.
    for y in range(h):
        for x in range(w):
            n = rng.randint(-9, 9)
            r, g, b = PAPER
            px[x, y] = (max(0, r + n), max(0, g + n), max(0, b + int(n * 0.8)))

    # Distressed fibre streaks, as seen in the references' aged ground.
    d = ImageDraw.Draw(img)
    for _ in range(int(w * h / 9000)):
        x = rng.randint(0, w)
        y = rng.randint(0, h)
        ln = rng.randint(12, 90)
        a = rng.choice([(214, 212, 206), (222, 220, 214), (208, 206, 200)])
        if rng.random() < 0.5:
            d.line([(x, y), (x + ln, y)], fill=a, width=1)
        else:
            d.line([(x, y), (x, y + ln)], fill=a, width=1)

    # Vignette: darken the outer edges slightly.
    vig = Image.new("L", (w, h), 0)
    vd = ImageDraw.Draw(vig)
    vd.ellipse([-w * 0.28, -h * 0.28, w * 1.28, h * 1.28], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(min(w, h) * 0.09))
    dark = Image.new("RGB", (w, h), (226, 224, 218))
    img = Image.composite(img, dark, vig)

    return img


def _hatch(d, box, step, angle, color=INK, width=1, jitter=0):
    """Cross-hatching inside a box at a given angle. The core engraving device."""
    x0, y0, x1, y1 = box
    diag = int(math.hypot(x1 - x0, y1 - y0)) + 2
    if angle == 45:
        for i in range(-diag, diag, step):
            j = random.randint(-jitter, jitter) if jitter else 0
            d.line([(x0 + i + j, y0), (x0 + i + j + (y1 - y0), y1)], fill=color, width=width)
    elif angle == -45:
        for i in range(-diag, diag, step):
            j = random.randint(-jitter, jitter) if jitter else 0
            d.line([(x0 + i + j, y0), (x0 + i + j - (y1 - y0), y1)], fill=color, width=width)
    elif angle == 0:
        for y in range(y0, y1, step):
            d.line([(x0, y), (x1, y)], fill=color, width=width)
    else:  # 90
        for x in range(x0, x1, step):
            d.line([(x, y0), (x, y1)], fill=color, width=width)


def _rosace(d, cx, cy, r, petals, rings=3, width=2):
    """
    A sacred-geometry flower: concentric rings with radiating petal arcs.

    The ring radius decays geometrically, so the loop stops as soon as a ring would
    invert (radius <= 0). Guarding here rather than trusting `rings` means any caller can
    pass a large count without producing an invalid bounding box.
    """
    for k in range(rings):
        rr = r * (1 - k * 0.26)
        if rr <= 2:
            break
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=INK, width=width)
        petal_r = rr * 0.44
        if petal_r <= 1:
            continue
        for i in range(petals):
            a = 2 * math.pi * i / petals + k * 0.2
            px_ = cx + math.cos(a) * rr * 0.55
            py_ = cy + math.sin(a) * rr * 0.55
            d.ellipse(
                [px_ - petal_r, py_ - petal_r, px_ + petal_r, py_ + petal_r],
                outline=INK, width=max(1, width - k),
            )


def _filigree(d, x, y, h, side, rng, width=1):
    """Vertical ornamental scrollwork down one edge."""
    cx = x
    for i in range(int(h / 26)):
        yy = y + i * 26
        s = 20 + (i % 4) * 7
        dirn = 1 if side == "left" else -1
        # Normalise the arc bounding box: Pillow requires x1 >= x0 and y1 >= y0, so the
        # box is ordered rather than built by adding a signed offset.
        ax0, ax1 = sorted((cx, cx + s * dirn))
        d.arc([ax0, yy - s / 2, ax1, yy + s / 2],
              0 if dirn > 0 else 180, 180 if dirn > 0 else 360,
              fill=INK, width=width)
        if i % 3 == 0:
            ex = cx + s * dirn * 0.9
            d.ellipse([ex - 3, yy - 3, ex + 3, yy + 3], outline=INK, width=1)


def _wing(d, x, y, span, up, rng, feathers=9):
    """A stylised wing: layered feather strokes sweeping outward and upward."""
    for f in range(feathers):
        t = f / max(1, feathers - 1)
        ln = span * (1 - 0.55 * t)
        ang = math.radians(-18 - t * 46) if up else math.radians(18 + t * 46)
        ex = x + math.cos(ang) * ln
        ey = y + math.sin(ang) * ln
        d.line([(x, y), (ex, ey)], fill=INK, width=2)
        # Secondary barb strokes give the feathered density of the references.
        for b in range(1, 5):
            bt = b / 5
            bx = x + (ex - x) * bt
            by = y + (ey - y) * bt
            d.line([(bx, by), (bx + 6, by + 5)], fill=INK, width=1)


# --------------------------------------------------------------------------------------
# Motif renderers
# --------------------------------------------------------------------------------------
def _draw_motif(img: Image.Image, motif: str, rng: random.Random) -> None:
    w, h = img.size
    d = ImageDraw.Draw(img)

    # Common frame: a panel rule with corner marks, as in the flash references.
    m = int(min(w, h) * 0.07)
    d.rectangle([m, m, w - m, h - m], outline=INK, width=2)
    for cx, cy in [(m, m), (w - m, m), (m, h - m), (w - m, h - m)]:
        d.rectangle([cx - 8, cy - 8, cx + 8, cy + 8], outline=INK, width=2)

    cx, cy = w // 2, h // 2

    if motif == "angel":
        _hatch(d, (m + 10, cy - 120, w - m - 10, h - m - 10), 7, 45, jitter=1)
        _wing(d, cx - 40, cy - 60, int(w * 0.36), True, rng)
        _wing(d, cx + 40, cy - 60, int(w * 0.36), True, rng)
        d.polygon([(cx, cy - 150), (cx - 46, cy + 130), (cx + 46, cy + 130)], outline=INK, width=3)
        d.ellipse([cx - 34, cy - 210, cx + 34, cy - 138], outline=INK, width=3)
        _hatch(d, (cx - 30, cy - 205, cx + 30, cy - 145), 6, -45)
        _rosace(d, cx, cy - 250, 44, 8, rings=2)

    elif motif == "sword":
        # Vertical ornate sword with a cruciform hilt.
        blade_top, blade_bot = m + 150, h - m - 120
        d.polygon([(cx - 16, blade_top + 120), (cx + 16, blade_top + 120),
                   (cx, blade_bot), ], outline=INK, width=3)
        _hatch(d, (cx - 14, blade_top + 130, cx + 14, blade_bot - 20), 6, 90)
        d.line([(cx, blade_top + 120), (cx, blade_bot)], fill=INK, width=2)
        d.line([(cx - 110, blade_top + 120), (cx + 110, blade_top + 120)], fill=INK, width=5)
        d.line([(cx, blade_top + 60), (cx, blade_top + 200)], fill=INK, width=5)
        _rosace(d, cx, blade_top + 40, 40, 6, rings=2)
        _filigree(d, m + 34, m + 60, h * 0.7, "left", rng)
        _filigree(d, w - m - 34, m + 60, h * 0.7, "right", rng)

    elif motif == "cross":
        d.line([(cx, m + 60), (cx, h - m - 60)], fill=INK, width=9)
        d.line([(m + 90, cy - 90), (w - m - 90, cy - 90)], fill=INK, width=9)
        for k in range(6):
            r = 40 + k * 46
            d.ellipse([cx - r, cy - 90 - r, cx + r, cy - 90 + r], outline=INK, width=1)
        _hatch(d, (cx + 20, cy - 70, w - m - 40, h - m - 30), 7, 45, jitter=1)
        _hatch(d, (m + 40, cy - 70, cx - 20, h - m - 30), 7, -45, jitter=1)

    elif motif == "dark":
        # Dark-ground piece: invert the tonal relationship (reference 4 behaviour).
        d.rectangle([m + 6, m + 6, w - m - 6, h - m - 6], fill=INK)
        _wing(d, cx - 30, cy, int(w * 0.33), True, rng)
        _wing(d, cx + 30, cy, int(w * 0.33), True, rng)
        for i in range(28):
            y = m + 30 + i * 26
            if y < h - m:
                d.line([(m + 20, y), (w - m - 20, y)], fill=PAPER, width=1)
        d.polygon([(cx, cy - 130), (cx - 40, cy + 140), (cx + 40, cy + 140)], outline=PAPER, width=3)
        _rosace_paper(d, cx, cy - 200, 46, 8)

    elif motif == "cathedral":
        # Gothic arch with tracery and a spire.
        arch_top = m + 90
        d.arc([m + 80, arch_top, w - m - 80, arch_top + (w - 2 * m - 160)], 180, 360,
              fill=INK, width=4)
        d.line([(m + 80, arch_top + (w - 2 * m - 160) / 2), (m + 80, h - m - 60)], fill=INK, width=4)
        d.line([(w - m - 80, arch_top + (w - 2 * m - 160) / 2), (w - m - 80, h - m - 60)],
               fill=INK, width=4)
        for i in range(7):
            x = m + 110 + i * (w - 2 * m - 220) / 6
            d.line([(x, arch_top + 130), (x, h - m - 60)], fill=INK, width=1)
        d.polygon([(cx, m + 30), (cx - 60, arch_top + 120), (cx + 60, arch_top + 120)],
                  outline=INK, width=3)
        _rosace(d, cx, arch_top + 200, 70, 12, rings=3)
        _hatch(d, (m + 20, h - m - 130, w - m - 20, h - m - 20), 8, 45, jitter=2)

    elif motif == "geometry":
        _rosace(d, cx, cy, int(min(w, h) * 0.34), 12, rings=4, width=2)
        for k in range(8):
            a = math.pi * k / 4
            d.line([(cx, cy), (cx + math.cos(a) * min(w, h) * 0.42,
                               cy + math.sin(a) * min(w, h) * 0.42)], fill=INK, width=1)
        for a in range(0, 360, 45):
            r = min(w, h) * 0.34
            rad = math.radians(a)
            d.ellipse([cx + math.cos(rad) * r - r * 0.5, cy + math.sin(rad) * r - r * 0.5,
                       cx + math.cos(rad) * r + r * 0.5, cy + math.sin(rad) * r + r * 0.5],
                      outline=INK, width=1)
        _filigree(d, m + 30, m + 40, h * 0.8, "left", rng)
        _filigree(d, w - m - 30, m + 40, h * 0.8, "right", rng)

    elif motif == "occult":
        _rosace(d, cx, cy - 80, 120, 7, rings=3)
        d.polygon([(cx, cy - 200), (cx + 104, cy + 30), (cx - 104, cy + 30)], outline=INK, width=3)
        d.polygon([(cx, cy + 40), (cx + 104, cy - 190), (cx - 104, cy - 190)], outline=INK, width=3)
        _hatch(d, (m + 30, cy + 60, w - m - 30, h - m - 30), 7, -45, jitter=1)
        for i, lbl in enumerate(["I", "II", "III"]):
            d.text((cx - 8 + i * 30 - 30, h - m - 60), lbl, fill=INK)

    elif motif == "backpiece":
        # A large, dense, symmetrical full-composition piece.
        _wing(d, cx - 60, cy - 40, int(w * 0.38), True, rng, feathers=11)
        _wing(d, cx + 60, cy - 40, int(w * 0.38), True, rng, feathers=11)
        _rosace(d, cx, cy - 260, 90, 10, rings=3)
        d.line([(cx, cy - 150), (cx, h - m - 70)], fill=INK, width=8)
        d.line([(cx - 130, cy + 40), (cx + 130, cy + 40)], fill=INK, width=8)
        _hatch(d, (m + 24, cy + 80, cx - 30, h - m - 30), 6, 45, jitter=1)
        _hatch(d, (cx + 30, cy + 80, w - m - 24, h - m - 30), 6, -45, jitter=1)
        _hatch(d, (m + 24, m + 24, w - m - 24, cy - 320), 9, 0)
        _filigree(d, m + 36, m + 50, h * 0.85, "left", rng)
        _filigree(d, w - m - 36, m + 50, h * 0.85, "right", rng)

    elif motif == "rosace":
        _rosace(d, cx, cy, int(min(w, h) * 0.36), 16, rings=5, width=2)
        for k in range(24):
            a = 2 * math.pi * k / 24
            r = min(w, h) * 0.36
            d.line([(cx + math.cos(a) * r, cy + math.sin(a) * r),
                    (cx + math.cos(a) * r * 1.32, cy + math.sin(a) * r * 1.32)], fill=INK, width=1)
        _hatch(d, (m + 20, h - m - 120, w - m - 20, h - m - 20), 8, 45, jitter=2)

    elif motif == "arch":
        aw = int(w * 0.62)
        ax0, ax1 = cx - aw // 2, cx + aw // 2
        top = m + 100
        d.arc([ax0, top, ax1, top + aw], 180, 360, fill=INK, width=4)
        d.line([(ax0, top + aw // 2), (ax0, h - m - 60)], fill=INK, width=4)
        d.line([(ax1, top + aw // 2), (ax1, h - m - 60)], fill=INK, width=4)
        d.polygon([(cx, top + 120), (cx - 34, h - m - 90), (cx + 34, h - m - 90)],
                  outline=INK, width=3)
        d.ellipse([cx - 26, top + 150, cx + 26, top + 202], outline=INK, width=3)
        _hatch(d, (ax0, h - m - 180, ax1, h - m - 60), 7, -45, jitter=1)
        _filigree(d, m + 30, m + 60, h * 0.75, "left", rng)
        _filigree(d, w - m - 30, m + 60, h * 0.75, "right", rng)

    elif motif == "triptych":
        pane_w = (w - 2 * m - 60) // 3
        for i in range(3):
            x0 = m + 20 + i * (pane_w + 10)
            d.rectangle([x0, m + 40, x0 + pane_w, h - m - 40], outline=INK, width=3)
            pcx = x0 + pane_w // 2
            if i == 0:
                _wing(d, pcx - 20, cy - 40, pane_w * 0.6, True, rng, feathers=7)
                d.polygon([(pcx, cy - 120), (pcx - 30, cy + 140), (pcx + 30, cy + 140)],
                          outline=INK, width=2)
            elif i == 1:
                d.line([(pcx, m + 90), (pcx, h - m - 90)], fill=INK, width=7)
                d.line([(x0 + 30, cy - 40), (x0 + pane_w - 30, cy - 40)], fill=INK, width=6)
                _rosace(d, pcx, cy + 90, 54, 6, rings=2)
            else:
                d.polygon([(pcx, cy - 130), (pcx - 36, cy + 150), (pcx + 36, cy + 150)],
                          outline=INK, width=3)
                _wing(d, pcx - 10, cy - 60, pane_w * 0.7, True, rng, feathers=8)
                d.line([(pcx, cy + 60), (pcx, h - m - 70)], fill=INK, width=5)
            _hatch(d, (x0 + 8, h - m - 150, x0 + pane_w - 8, h - m - 50), 8, 45, jitter=2)

    elif motif == "crown":
        _hatch(d, (m + 30, cy - 60, w - m - 30, h - m - 30), 8, -45, jitter=2)
        base_y = cy - 60
        d.polygon([(cx - 130, base_y), (cx + 130, base_y), (cx + 130, base_y + 60),
                   (cx - 130, base_y + 60)], outline=INK, width=3)
        for i in range(5):
            x = cx - 100 + i * 50
            d.polygon([(x, base_y), (x + 25, base_y - 90), (x + 50, base_y)], outline=INK, width=3)
            d.ellipse([x + 18, base_y - 112, x + 32, base_y - 98], outline=INK, width=2)
        for i in range(9):
            x = cx - 120 + i * 30
            d.line([(x, base_y + 60), (x + 40, h - m - 40)], fill=INK, width=2)
            d.ellipse([x + 30, h - m - 66, x + 42, h - m - 54], outline=INK, width=2)


def _rosace_paper(d, cx, cy, r, petals):
    """Rosace drawn in paper-white, for dark-ground pieces."""
    for k in range(2):
        rr = r * (1 - k * 0.28)
        if rr <= 2:
            break
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=PAPER, width=2)
        pr = rr * 0.42
        if pr <= 1:
            continue
        for i in range(petals):
            a = 2 * math.pi * i / petals
            px_ = cx + math.cos(a) * rr * 0.5
            py_ = cy + math.sin(a) * rr * 0.5
            d.ellipse([px_ - pr, py_ - pr, px_ + pr, py_ + pr], outline=PAPER, width=1)


# --------------------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------------------
def render_composition(comp: Composition) -> bytes:
    """Render one composition to PNG bytes."""
    rng = random.Random(comp.seed)
    img = _paper(comp.width, comp.height, rng)
    _draw_motif(img, comp.motif, rng)

    # A light final blur unifies the hatching into the paper the way ink bleed would,
    # then a sharpen restores the line definition. This keeps the dither stable.
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    img = img.filter(ImageFilter.UnsharpMask(radius=1.4, percent=70, threshold=2))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_all() -> list[tuple[Composition, bytes]]:
    return [(c, render_composition(c)) for c in COMPOSITIONS]
