"""
Image pipeline tests.

The dither test is a REGRESSION GUARD, not a smoke test. An earlier implementation
produced high-frequency static instead of a halftone screen, and it was only caught by
looking at the output. These tests measure the structural properties that distinguish a
real screen from noise, so the regression cannot return silently.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from services.images import (
    BAYER_8,
    DERIVATIVE_WIDTHS,
    generate_all,
    generate_derivatives,
    generate_dither,
    generate_lqip,
    open_image,
    probe_dimensions,
)


@pytest.fixture
def paper_art() -> bytes:
    """A synthetic 'engraving': paper ground with dark linework, which is the hard case."""
    img = Image.new("RGB", (800, 1000), (240, 239, 234))
    px = img.load()
    # Diagonal cross-hatching in ink
    for y in range(1000):
        for x in range(800):
            if (x + y) % 7 == 0 or (x - y) % 11 == 0:
                px[x, y] = (10, 10, 12)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def dark_art() -> bytes:
    """A dark-ground piece: the opposite tonal distribution."""
    img = Image.new("RGB", (600, 600), (8, 6, 6))
    px = img.load()
    for y in range(600):
        for x in range(600):
            if (x * y) % 5 == 0:
                px[x, y] = (220, 210, 200)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# --------------------------------------------------------------------------------------
# Derivatives
# --------------------------------------------------------------------------------------
def test_derivatives_are_generated_in_expected_sizes(paper_art):
    variants = generate_derivatives(paper_art)
    widths = [v.width for v in variants]
    assert widths, "at least one derivative must exist"
    assert widths == sorted(widths), "derivatives should be in ascending width order"
    for v in variants:
        assert v.width in DERIVATIVE_WIDTHS
        assert v.kind == "derivative"


def test_derivatives_never_upscale_beyond_source():
    """A 500px source must not be served as a fake 2400px file."""
    img = Image.new("RGB", (500, 500), (240, 240, 240))
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    variants = generate_derivatives(buf.getvalue())
    assert all(v.width <= 500 for v in variants), "upscaling must be refused"


def test_tiny_source_still_yields_a_derivative():
    """Small uploads must not produce an empty variant list."""
    img = Image.new("RGB", (80, 80), (200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    variants = generate_derivatives(buf.getvalue())
    assert len(variants) == 1
    assert variants[0].width == 80


def test_derivatives_are_webp(paper_art):
    for v in generate_derivatives(paper_art):
        header = v.content[:12]
        assert b"WEBP" in header, "derivatives must be WebP"


def test_aspect_ratio_is_preserved(paper_art):
    """800x1000 in -> every derivative keeps the 0.8 ratio."""
    for v in generate_derivatives(paper_art):
        assert abs((v.width / v.height) - 0.8) < 0.02, f"{v.width}x{v.height} distorted"


# --------------------------------------------------------------------------------------
# LQIP
# --------------------------------------------------------------------------------------
def test_lqip_is_small(paper_art):
    lqip = generate_lqip(paper_art)
    assert lqip.kind == "lqip"
    assert lqip.width == 24
    assert len(lqip.content) < 2000, "LQIP must stay tiny enough to inline"


# --------------------------------------------------------------------------------------
# Dither — the regression guards
# --------------------------------------------------------------------------------------
def _dot_coverage(variant) -> float:
    """
    Fraction of pixels that carry a dot (high blue channel) versus ground.

    Measured on the BLUE channel because the plate is cobalt-on-black: converting to
    greyscale would read cobalt as dark and report a false zero.
    """
    img = Image.open(io.BytesIO(variant.content)).convert("RGB")
    px = img.load()
    w, h = img.size
    dots = total = 0
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            total += 1
            if px[x, y][2] > 100:
                dots += 1
    return dots / total if total else 0.0


def test_dither_produces_dots_not_a_blank_plate(paper_art):
    """Guard: the original bug produced a plate that was mostly one value."""
    d = generate_dither(paper_art, width=600, threshold=140)
    coverage = _dot_coverage(d)
    assert 0.05 < coverage < 0.90, f"dot coverage {coverage:.2%} is degenerate"


def test_dither_is_structured_not_noise(paper_art):
    """
    Regression guard for the core bug.

    A true ordered-halftone screen rendered at reduced resolution and upscaled with
    NEAREST produces square cells of size `scale`. That means the pattern must be
    IDENTICAL within each cell block -- neighbouring pixels inside a cell agree, while
    pixels a full cell apart differ more often.

    Random noise has no such structure: intra-cell agreement would be no higher than
    inter-cell agreement. This test measures exactly that difference.
    """
    d = generate_dither(paper_art, width=600, threshold=140)
    img = Image.open(io.BytesIO(d.content)).convert("RGB")
    px = img.load()
    w, h = img.size

    def dot(x, y) -> int:
        return 1 if px[x, y][2] > 100 else 0

    # Sample a large region to get stable statistics.
    x0, y0, n = w // 4, h // 4, 120

    # Intra-cell agreement: do adjacent pixels match?
    adj_match = adj_total = 0
    for y in range(y0, y0 + n):
        for x in range(x0, x0 + n - 1):
            adj_total += 1
            adj_match += dot(x, y) == dot(x + 1, y)

    # Inter-cell agreement: do pixels 3 apart (one cell width) match?
    far_match = far_total = 0
    for y in range(y0, y0 + n):
        for x in range(x0, x0 + n - 3):
            far_total += 1
            far_match += dot(x, y) == dot(x + 3, y)

    adj = adj_match / adj_total
    far = far_match / far_total

    # Structured cells: adjacent pixels agree MORE than pixels a cell apart.
    assert adj > far, (
        f"pattern lacks cell structure (adjacent agreement {adj:.3f} <= "
        f"cell-distance agreement {far:.3f}) -- this is the noise regression"
    )
    # And the structure must be strong, not marginal.
    assert (adj - far) > 0.10, f"cell structure too weak (delta {adj - far:.3f})"


def test_threshold_changes_dot_density(dark_art):
    """Threshold must actually modulate the plate -- it is a per-image control."""
    low = _dot_coverage(generate_dither(dark_art, width=400, threshold=90))
    high = _dot_coverage(generate_dither(dark_art, width=400, threshold=200))
    assert low > high, "a lower threshold must produce denser dots"


def test_dither_preserves_aspect_ratio(paper_art):
    d = generate_dither(paper_art, width=600)
    assert abs((d.width / d.height) - 0.8) < 0.02


def test_dither_width_is_respected(paper_art):
    d = generate_dither(paper_art, width=480)
    assert d.width == 480


def test_dither_never_upscales(dark_art):
    """600px source, asked for 1600 -> must stay at 600."""
    d = generate_dither(dark_art, width=1600)
    assert d.width == 600


def test_bayer_matrix_is_a_valid_permutation():
    """The 8x8 matrix must contain every value 0..63 exactly once."""
    flat = [v for row in BAYER_8 for v in row]
    assert sorted(flat) == list(range(64))


# --------------------------------------------------------------------------------------
# Utilities
# --------------------------------------------------------------------------------------
def test_open_image_flattens_transparency_to_paper():
    """
    A transparent PNG must resolve to paper, not to void.

    The art direction is ink on paper; compositing onto black would silently invert the
    tonal relationship of every transparent upload.
    """
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    result = open_image(buf.getvalue())
    assert result.mode == "RGB"
    # Fully transparent -> paper white, not black.
    assert result.getpixel((50, 50))[0] > 200


def test_probe_dimensions(paper_art):
    assert probe_dimensions(paper_art) == (800, 1000)


def test_generate_all_returns_every_variant(paper_art):
    derivs, dither, lqip = generate_all(paper_art, dither_width=600)
    assert len(derivs) >= 1
    assert dither.kind == "dither"
    assert lqip.kind == "lqip"
