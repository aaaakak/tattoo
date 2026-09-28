"""
Image pipeline: derivatives, LQIP placeholders and the halftone/dither sibling.

Framework-free by design — no Django or FastAPI imports. Both stacks call the same
functions, so the dither algorithm exists exactly once. See docs/architecture.md §5.

The dither variant is generated at UPLOAD time, never at request time. That is what makes
the signature dither-to-full transition cost zero runtime CPU for the visitor.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

# --------------------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------------------

# Derivative widths. Chosen against the layout: cards render at ~420px, editorial runs
# at ~800px, detail heroes at ~1600px, and retina doubles the largest.
DERIVATIVE_WIDTHS: tuple[int, ...] = (400, 800, 1200, 1600, 2400)

# Below this width, intricate engraving destroys into noise — so 400 is the floor for the
# full-fidelity variants. The halftone variant is the deliberate exception (see
# docs/art-direction.md, "detail floor").
MIN_DETAIL_WIDTH = 400

# LQIP: a 24px blur placeholder inlined as a data URL for zero-CLS image loading.
LQIP_WIDTH = 24

WEBP_QUALITY = 82
AVIF_ENABLED = False  # Pillow's AVIF support is still optional; WebP is the safe default.

# Bayer 8x8 ordered-dither threshold matrix. Ordered (not Floyd-Steinberg) deliberately:
# it produces a stable, repeatable pattern that reads as a deliberate halftone screen
# rather than random noise, which is the whole point of the aesthetic.
BAYER_8 = [
    [0, 32, 8, 40, 2, 34, 10, 42],
    [48, 16, 56, 24, 50, 18, 58, 26],
    [12, 44, 4, 36, 14, 46, 6, 38],
    [60, 28, 52, 20, 62, 30, 54, 22],
    [3, 35, 11, 43, 1, 33, 9, 41],
    [51, 19, 59, 27, 49, 17, 57, 25],
    [15, 47, 7, 39, 13, 45, 5, 37],
    [63, 31, 55, 23, 61, 29, 53, 21],
]


@dataclass(frozen=True)
class Variant:
    """One generated image file."""

    kind: str  # "derivative" | "dither" | "lqip"
    width: int
    height: int
    content: bytes
    suffix: str = ".webp"


# --------------------------------------------------------------------------------------
# Derivative generation
# --------------------------------------------------------------------------------------
def open_image(data: bytes) -> Image.Image:
    """
    Decode bytes into an RGB image, applying EXIF orientation.

    ``ImageOps.exif_transpose`` matters: a phone photo of a tattoo is frequently stored
    rotated with an orientation flag, and ignoring it renders the artwork sideways.
    """
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        # Flatten transparency onto paper white rather than black — the art direction is
        # ink on paper, so a transparent PNG should resolve to paper, not to void.
        background = Image.new("RGB", img.size, (240, 239, 234))
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1])
            img = background
        else:
            img = img.convert("RGB")
    return img.convert("RGB") if img.mode == "L" else img


def generate_derivatives(
    data: bytes, widths: tuple[int, ...] = DERIVATIVE_WIDTHS
) -> list[Variant]:
    """
    Produce resized WebP variants, never upscaling beyond the source.

    Upscaling is refused rather than performed: a 900px source must not be served as a
    fake 2400px file that only increases bytes without adding detail.
    """
    img = open_image(data)
    src_w, src_h = img.size
    out: list[Variant] = []

    for width in widths:
        if width > src_w:
            continue  # never upscale
        ratio = width / src_w
        height = max(1, round(src_h * ratio))
        resized = img.resize((width, height), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        resized.save(buf, format="WEBP", quality=WEBP_QUALITY, method=5)
        out.append(Variant("derivative", width, height, buf.getvalue()))

    # Always guarantee at least one derivative, even for a tiny source.
    if not out:
        buf = io.BytesIO()
        img.save(buf, format="WEBP", quality=WEBP_QUALITY, method=5)
        out.append(Variant("derivative", src_w, src_h, buf.getvalue()))

    return out


# --------------------------------------------------------------------------------------
# LQIP
# --------------------------------------------------------------------------------------
def generate_lqip(data: bytes, width: int = LQIP_WIDTH) -> Variant:
    """A tiny heavily-blurred placeholder, encoded as WebP bytes."""
    img = open_image(data)
    ratio = width / img.width
    height = max(1, round(img.height * ratio))
    small = img.resize((width, height), Image.Resampling.LANCZOS)
    small = small.filter(ImageFilter.GaussianBlur(1.2))
    buf = io.BytesIO()
    small.save(buf, format="WEBP", quality=40)
    return Variant("lqip", width, height, buf.getvalue())


# --------------------------------------------------------------------------------------
# Halftone / dither — the signature treatment
# --------------------------------------------------------------------------------------
def generate_dither(
    data: bytes,
    width: int = 1600,
    *,
    threshold: int = 118,
    contrast: float = 1.15,
    sharpen: bool = True,
) -> Variant:
    """
    Render the artwork as a cobalt-on-black ordered-halftone plate.

    Algorithm:
      1. Decode and (optionally) upscale to the requested working width, capped at source.
      2. Convert to luminance (perceptual weights, not a flat average — flat averaging
         loses the contrast between dark linework and paper that makes engraving read).
      3. Apply an S-curve via autocontrast + contrast enhancement, so intermediate paper
         tones resolve to distinct dots instead of a flat grey mush.
      4. Ordered-dither against the Bayer 8x8 matrix: each pixel becomes a dot when its
         luminance crosses the local threshold.
      5. Tone-map the result into the site's cobalt highlight on the void ground.

    ``threshold`` is deliberately a parameter and is expected to be set PER IMAGE.
    High-key paper-ground artwork (references 1-3 in docs/art-direction.md) needs a low
    threshold to keep thin lines legible; dark-ground artwork (reference 4) needs a high
    one or it crushes to solid cobalt.
    """
    img = open_image(data)

    # Work at the requested width, never upscaling.
    target = min(width, img.width)
    ratio = target / img.width
    work = img.resize((target, max(1, round(img.height * ratio))), Image.Resampling.LANCZOS)

    # Luminance with perceptual weights.
    gray = work.convert("L")

    # ----------------------------------------------------------------------------------
    # CRITICAL: pre-blur before dithering.
    #
    # A per-pixel 1-bit decision destroys anything thinner than one dot cell. Fine-line
    # engraving is *made* of 1-2px strokes, so deciding at full resolution shatters every
    # line into disconnected specks -- measured and confirmed: the plate read as noise.
    #
    # The fix is the standard halftone method: low-pass the image first so each dot cell
    # sums the tone of its neighbourhood rather than sampling one pixel. The dot then
    # carries the *average* of the linework it covers, which is exactly how a printed
    # screen reproduces a line drawing. A Gaussian of radius ~0.6 cell widths is the
    # conventional choice.
    # ----------------------------------------------------------------------------------
    gray = gray.filter(ImageFilter.GaussianBlur(radius=0.9))

    # Resolve the tonal range into distinct dots.
    gray = ImageOps.autocontrast(gray, cutoff=1)
    gray = ImageEnhance.Contrast(gray).enhance(contrast)
    if sharpen:
        # Engraving is line-based; sharpening preserves thin strokes before dithering.
        gray = gray.filter(ImageFilter.UnsharpMask(radius=1.2, percent=90, threshold=3))

    src = gray.load()
    w, h = gray.size

    # ----------------------------------------------------------------------------------
    # Render the screen at REDUCED resolution, then upscale.
    #
    # This is what makes the result read as a printed halftone rather than digital static.
    # At full resolution each screen cell is 1px, so the pattern is finer than the eye can
    # integrate and it registers as noise. Rendering at 1/`scale` and upscaling with
    # NEAREST makes each cell a visible `scale`x`scale` block -- the dot becomes an object
    # the eye can read, which is precisely how commercial halftone screens work.
    #
    # scale=3 -> each cell is a 3x3 block. Rebuilt from the native w,h below.
    # ----------------------------------------------------------------------------------
    scale = max(2, min(4, round(w / 400)))  # bigger images get chunkier cells
    sw, sh = max(1, w // scale), max(1, h // scale)
    small = gray.resize((sw, sh), Image.Resampling.LANCZOS)
    src = small.load()
    w, h = sw, sh

    out = Image.new("L", (w, h), 0)
    dst = out.load()

    # ----------------------------------------------------------------------------------
    # Ordered dithering, done properly.
    #
    # The Bayer matrix holds values 0..63. Each value is mapped to the SAME 0..255 range
    # as the source luminance, then offset to sit evenly AROUND the threshold:
    #
    #     bias = (m / 64 - 0.5) * spread          ->  a symmetric +/- spread/2 window
    #
    # An earlier version used (m * 4) - 128, a +/-128 swing on a 0..255 scale. That is
    # more than 4x too wide: it does not modulate the threshold, it replaces it, producing
    # high-frequency static instead of a structured screen. The spread must stay small
    # relative to the tonal range so that neighbouring cells differ by a *fine* step and
    # the eye integrates them into a smooth tone.
    #
    # spread=64 means each adjacent Bayer step shifts the decision point by 1/64th of the
    # range -- fine enough to render gradients, coarse enough to be visible as a screen.
    # ----------------------------------------------------------------------------------
    spread = 64
    half = spread / 2.0

    for y in range(h):
        brow = BAYER_8[y & 7]
        for x in range(w):
            m = brow[x & 7]
            bias = (m / 64.0) * spread - half
            # Polarity: INK produces dots, paper stays as ground.
            # The artwork is ink-on-paper, so the ink value is (255 - luminance). The
            # dot fires when the ink is dense enough, modulated by the Bayer bias:
            #
            #   low threshold  -> more of the drawing becomes dots (denser, bolder plate)
            #   high threshold -> only the heaviest strokes survive (sparser, lighter)
            #
            # This is why the threshold is a PER-IMAGE field: a high-key engraving needs a
            # low threshold to keep its thin lines, while a dark-ground piece needs a high
            # one or it crushes into a solid block.
            ink = 255 - src[x, y]
            dst[x, y] = 255 if ink + bias >= threshold else 0

    # Tone-map: 0 -> void (ground), 255 -> cobalt (ink dots).
    # On the dark ground the engraving reads as cobalt linework, matching how design
    # reference 3 renders a white engraving on a coloured field.
    plate = ImageOps.colorize(out, black="#050507", white="#6060F0", mid="#1B2CFF")

    # ----------------------------------------------------------------------------------
    # Upscale to the final size with NEAREST.
    #
    # The screen was rendered at `cell / scale` pixels, so each screen cell occupies a
    # block of `scale`x`scale` pixels. NEAREST preserves those blocks exactly as hard-
    # edged dot cells. A smoothing filter here would blur the dots back into noise and
    # undo the entire point of the treatment.
    # ----------------------------------------------------------------------------------
    if scale > 1:
        plate = plate.resize((target, max(1, round(img.height * ratio))), Image.Resampling.NEAREST)

    buf = io.BytesIO()
    plate.save(buf, format="WEBP", quality=88, method=5)
    return Variant("dither", plate.width, plate.height, buf.getvalue())


def generate_all(data: bytes, *, dither_width: int = 1600, dither_threshold: int = 118):
    """
    Convenience wrapper used by the upload pipeline: every variant for one asset.

    Returns (derivatives, dither, lqip).
    """
    return (
        generate_derivatives(data),
        generate_dither(data, width=dither_width, threshold=dither_threshold),
        generate_lqip(data),
    )


def probe_dimensions(data: bytes) -> tuple[int, int]:
    """Read intrinsic dimensions without retaining the full image."""
    with Image.open(io.BytesIO(data)) as img:
        img = ImageOps.exif_transpose(img)
        return img.size


def build_dither_filename(original_name: str) -> str:
    """`art/foo.png` -> `art/foo__dither.webp`"""
    p = Path(original_name)
    return str(p.with_name(f"{p.stem}__dither{p.suffix}")).rsplit(".", 1)[0] + ".webp"
