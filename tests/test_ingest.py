"""
Upload validation and ingest pipeline tests.

Security-relevant: the validation function is the only barrier between an arbitrary
upload and the filesystem, so each of its four checks is tested independently. A single
lax check would let a crafted file through, and each check alone is bypassable.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from apps.core.ingest import UploadValidationError, ingest_image, validate_upload
from apps.core.models import MediaAsset


def _png(width=200, height=250, colour=(200, 200, 200)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), colour).save(buf, format="PNG")
    return buf.getvalue()


def _jpg(width=200, height=250) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (180, 180, 180)).save(buf, format="JPEG")
    return buf.getvalue()


# --------------------------------------------------------------------------------------
# Validation — each check independently
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize("name", ["a.jpg", "a.jpeg", "a.png", "a.webp", "a.gif", "a.avif"])
def test_accepted_extensions(name):
    validate_upload(name, _png() if name.endswith(".png") else _jpg())


@pytest.mark.parametrize("name", ["a.svg", "a.svgz"])
def test_svg_is_rejected(name):
    """SVG is an XSS vector when served from the same origin. It must never be accepted."""
    with pytest.raises(UploadValidationError, match="SVG"):
        validate_upload(name, b"<svg xmlns='http://www.w3.org/2000/svg'></svg>")


@pytest.mark.parametrize("name", ["a.exe", "a.php", "a.py", "a.sh", "a.html", "a", "a.tar.gz"])
def test_disallowed_extensions_rejected(name):
    with pytest.raises(UploadValidationError):
        validate_upload(name, _png())


def test_oversize_is_rejected():
    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (2 * 1024 * 1024)
    with pytest.raises(UploadValidationError, match="too large"):
        validate_upload("big.png", big, max_mb=1)


def test_tiny_file_is_rejected():
    with pytest.raises(UploadValidationError, match="empty or corrupt"):
        validate_upload("tiny.png", b"\x89PNG\r\n\x1a\n")


def test_renamed_executable_is_rejected():
    """
    An .png extension with non-image content must fail the magic-byte check.

    This is the attack the extension check alone cannot stop.
    """
    fake = b"#!/bin/sh\necho pwned\n" + b"\x00" * 200
    with pytest.raises(UploadValidationError, match="does not match its extension"):
        validate_upload("innocent.png", fake)


def test_truncated_image_fails_pillow_verify():
    """Correct magic bytes but corrupt body must be caught by verify()."""
    good = _png()
    truncated = good[: len(good) // 2]
    with pytest.raises(UploadValidationError):
        validate_upload("broken.png", truncated)


# --------------------------------------------------------------------------------------
# Ingest
# --------------------------------------------------------------------------------------
@pytest.mark.django_db
def test_ingest_creates_full_variant_chain():
    original = ingest_image(filename="art/test.png", content=_png(800, 1000), alt_text="Test piece")

    assert original.kind == MediaAsset.Kind.ORIGINAL
    assert (original.width, original.height) == (800, 1000)
    assert original.sha256

    siblings = MediaAsset.objects.filter(sha256=original.sha256)
    kinds = set(siblings.values_list("kind", flat=True))
    assert kinds == {"original", "derivative", "dither", "lqip"}


@pytest.mark.django_db
def test_ingest_is_idempotent_for_identical_bytes():
    """The same bytes ingested twice must not duplicate the original."""
    data = _png(400, 500)
    a = ingest_image(filename="x.png", content=data)
    b = ingest_image(filename="y.png", content=data)
    assert a.pk == b.pk
    assert MediaAsset.objects.filter(kind=MediaAsset.Kind.ORIGINAL).count() == 1


@pytest.mark.django_db
def test_ingest_does_not_collide_on_repeat_with_variants_present():
    """
    Re-ingesting while variant rows exist must not raise.

    Regression guard: an earlier version hit the unique constraint because the dedup
    check only looked at the ORIGINAL, not at its derivative/dither/lqip siblings.
    """
    data = _png(600, 700)
    ingest_image(filename="a.png", content=data)
    MediaAsset.objects.filter(kind=MediaAsset.Kind.ORIGINAL).delete()
    # Now the original is gone but variants remain -- ingest must handle this.
    ingest_image(filename="a.png", content=data)
    assert MediaAsset.objects.filter(kind=MediaAsset.Kind.ORIGINAL).count() == 1


@pytest.mark.django_db
def test_ingest_respects_per_image_dither_threshold():
    """The threshold is a per-asset control, not a global constant."""
    dark = ingest_image(filename="dark.png", content=_png(500, 500, (10, 10, 10)), dither_threshold=170)
    light = ingest_image(filename="light.png", content=_png(500, 500, (240, 240, 240)), dither_threshold=90)

    assert dark.dither_threshold == 170
    assert light.dither_threshold == 90
    # Different thresholds must produce different plates.
    d1 = MediaAsset.objects.get(sha256=dark.sha256, kind=MediaAsset.Kind.DITHER)
    d2 = MediaAsset.objects.get(sha256=light.sha256, kind=MediaAsset.Kind.DITHER)
    assert d1.file.read() != d2.file.read()


@pytest.mark.django_db
def test_ingest_rejects_invalid_upload_before_writing():
    """Validation must happen before any row or file is created."""
    before = MediaAsset.objects.count()
    with pytest.raises(UploadValidationError):
        ingest_image(filename="evil.svg", content=b"<svg/>")
    assert MediaAsset.objects.count() == before


@pytest.mark.django_db
def test_variants_for_resolves_the_chain():
    from apps.core.ingest import variants_for

    original = ingest_image(filename="art/chain.png", content=_png(900, 1200), alt_text="Chain")
    v = variants_for(original)

    assert v["dither"] is not None
    assert v["lqip"] is not None
    assert v["by_width"], "derivative widths should be populated"
    assert v["largest"].width >= max(v["by_width"])
    assert v["dither"].kind == MediaAsset.Kind.DITHER


@pytest.mark.django_db
def test_upload_path_does_not_double_the_media_prefix():
    """
    MEDIA_ROOT already points at the media dir, so the upload path must be relative.

    Regression guard: an earlier version produced media/media/2026/09/... because the
    path function included 'media/' itself.
    """
    original = ingest_image(filename="p.png", content=_png())
    assert not original.file.name.startswith("media/media/")
    assert "/" in original.file.name  # still date-partitioned


@pytest.mark.django_db
def test_derivatives_are_never_upscaled_for_small_sources():
    original = ingest_image(filename="small.png", content=_png(300, 300))
    widths = list(
        MediaAsset.objects.filter(
            sha256=original.sha256, kind=MediaAsset.Kind.DERIVATIVE
        ).values_list("width", flat=True)
    )
    assert all(w <= 300 for w in widths), f"upscaled derivatives found: {widths}"
