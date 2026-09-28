"""
MediaAsset ingestion: validate, store, and generate every derivative.

This module is the bridge between raw uploaded bytes and the fully-populated MediaAsset
the templates consume. It is called by:

  - the admin upload path (Phase 4)
  - the booking reference-image upload (Phase 7)
  - the sample-art seeding command (this phase)

Everything it does is synchronous and bounded: derivatives plus one dither plate take
~0.2-1.5s for a typical upload, which is acceptable at upload time and is what keeps the
dither transition free at request time.
"""

from __future__ import annotations

import hashlib
import io
import logging
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction

from apps.core.models import MediaAsset
from services import images as img_service

logger = logging.getLogger("apps")

# Validation limits. Enforced server-side; client-side checks are advisory only.
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}
ALLOWED_MIME_PREFIX = "image/"
# SVG is deliberately excluded: it is an XSS vector when served from the same origin.
BLOCKED_EXTENSIONS = {".svg", ".svgz"}
MAX_UPLOAD_MB = 12


class UploadValidationError(ValidationError):
    """Raised when an upload fails validation. Message is safe to show the user."""


def validate_upload(filename: str, content: bytes, max_mb: int = MAX_UPLOAD_MB) -> None:
    """
    Validate an upload before doing any work with it.

    Four independent checks, because each alone is bypassable:
      1. Extension against the allow-list (and an explicit block-list for SVG).
      2. Size cap, checked before decoding so a decompression bomb is refused early.
      3. Magic-byte sniff, so a renamed executable is rejected.
      4. Pillow verify(), which proves it is a decodable image and not a crafted file.

    Passing all four is the bar. Any one alone would let something through.
    """
    ext = Path(filename).suffix.lower()

    if ext in BLOCKED_EXTENSIONS:
        raise UploadValidationError(
            "SVG uploads are not accepted. Please upload a JPEG, PNG or WebP image."
        )
    if ext not in ALLOWED_EXTENSIONS:
        raise UploadValidationError(
            f"Unsupported file type '{ext or 'none'}'. "
            f"Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
        )

    max_bytes = max_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise UploadValidationError(
            f"File is too large ({len(content) / 1024 / 1024:.1f} MB). "
            f"Maximum is {max_mb} MB."
        )
    if len(content) < 64:
        raise UploadValidationError("File appears to be empty or corrupt.")

    # Magic bytes for the formats we accept.
    magic_ok = (
        content[:3] == b"\xff\xd8\xff"          # JPEG
        or content[:8] == b"\x89PNG\r\n\x1a\n"  # PNG
        or content[:6] in (b"GIF87a", b"GIF89a")  # GIF
        or content[:4] == b"RIFF"               # WebP (RIFF....WEBP)
        or content[4:12] == b"ftypavif"         # AVIF
    )
    if not magic_ok:
        raise UploadValidationError(
            "File content does not match its extension. Please upload a real image."
        )

    # Pillow verify() is the strongest check: it parses the actual image structure.
    try:
        from PIL import Image

        probe = Image.open(io.BytesIO(content))
        probe.verify()
    except Exception as exc:
        raise UploadValidationError("File could not be read as an image.") from exc


@transaction.atomic
def ingest_image(
    *,
    filename: str,
    content: bytes,
    alt_text: str = "",
    dither_width: int = 1600,
    dither_threshold: int = 118,
    max_mb: int = MAX_UPLOAD_MB,
) -> MediaAsset:
    """
    Validate, store and generate every variant for one image.

    Returns the ORIGINAL MediaAsset. Derivative, dither and LQIP assets are created as
    separate rows sharing the same ``sha256`` but differing in ``kind`` and
    ``variant_key`` -- which is what the ``uniq_asset_sha_kind_variant`` constraint
    permits, and why the same image ingested twice does not duplicate storage.
    """
    validate_upload(filename, content, max_mb=max_mb)

    digest = hashlib.sha256(content).hexdigest()

    # Deduplicate: the same bytes with the same kind already exist.
    existing = MediaAsset.objects.filter(sha256=digest, kind=MediaAsset.Kind.ORIGINAL).first()
    if existing is not None:
        logger.info("ingest_image: deduplicated %s", filename)
        return existing

    width, height = img_service.probe_dimensions(content)

    original = MediaAsset(
        kind=MediaAsset.Kind.ORIGINAL,
        variant_key="",
        width=width,
        height=height,
        byte_size=len(content),
        sha256=digest,
        alt_text=alt_text,
        # Persist the settings the plate was actually generated with. Storing the default
        # here while rendering at a different threshold would make the record lie about
        # how the image was treated -- and would break any later re-generation.
        dither_threshold=dither_threshold,
        dither_width=dither_width,
    )
    original.file.save(Path(filename).name, ContentFile(content), save=False)
    original.save()

    stem = Path(original.file.name).stem
    parent = str(Path(original.file.name).parent)

    # --- Derivatives ---------------------------------------------------------
    # Idempotent: re-ingesting the same bytes reuses the variant rows rather than
    # colliding with uniq_asset_sha_kind_variant. This matters because a reset can
    # legitimately leave orphaned variants behind.
    for variant in img_service.generate_derivatives(content):
        key = str(variant.width)
        if MediaAsset.objects.filter(
            sha256=digest, kind=MediaAsset.Kind.DERIVATIVE, variant_key=key
        ).exists():
            continue
        asset = MediaAsset(
            kind=MediaAsset.Kind.DERIVATIVE,
            width=variant.width,
            height=variant.height,
            byte_size=len(variant.content),
            sha256=digest,
            variant_key=key,
            alt_text=alt_text,
        )
        name = f"{parent}/{stem}__{variant.width}.webp"
        asset.file.save(name, ContentFile(variant.content), save=False)
        asset.save()

    # --- Dither plate --------------------------------------------------------
    dither = img_service.generate_dither(
        content, width=dither_width, threshold=dither_threshold
    )
    dither_asset = None
    if not MediaAsset.objects.filter(
        sha256=digest, kind=MediaAsset.Kind.DITHER, variant_key="dither"
    ).exists():
        dither_asset = MediaAsset(
            kind=MediaAsset.Kind.DITHER,
            width=dither.width,
            height=dither.height,
            byte_size=len(dither.content),
            sha256=digest,
            variant_key="dither",
            alt_text=alt_text,
        )
        dither_asset.file.save(
            f"{parent}/{stem}__dither.webp",
            ContentFile(dither.content),
            save=False,
        )
        dither_asset.save()

    # --- LQIP ----------------------------------------------------------------
    lqip = img_service.generate_lqip(content)
    lqip_asset = None
    if not MediaAsset.objects.filter(
        sha256=digest, kind=MediaAsset.Kind.LQIP, variant_key="lqip"
    ).exists():
        lqip_asset = MediaAsset(
            kind=MediaAsset.Kind.LQIP,
            width=lqip.width,
            height=lqip.height,
            byte_size=len(lqip.content),
            sha256=digest,
            variant_key="lqip",
            alt_text=alt_text,
        )
        lqip_asset.file.save(
            f"{parent}/{stem}__lqip.webp",
            ContentFile(lqip.content),
            save=False,
        )
        lqip_asset.save()

    logger.info(
        "ingest_image: %s -> %dx%d, %d derivatives + dither + lqip",
        filename, width, height, len(img_service.DERIVATIVE_WIDTHS),
    )
    return original


def variants_for(asset: MediaAsset) -> dict[str, object]:
    """
    Resolve the sibling assets for one image, for template use.

    Returns dict with keys: derivative map by width, ``dither``, ``lqip``.
    """
    digest = asset.sha256
    # All variants of one image share the ORIGINAL's content hash.
    siblings = MediaAsset.objects.filter(sha256=digest) if digest else MediaAsset.objects.none()
    by_width = {}
    dither = lqip = None
    for s in siblings:
        if s.kind == MediaAsset.Kind.DERIVATIVE:
            by_width[s.width] = s
        elif s.kind == MediaAsset.Kind.DITHER:
            dither = s
        elif s.kind == MediaAsset.Kind.LQIP:
            lqip = s
    return {
        "by_width": dict(sorted(by_width.items())),
        "dither": dither,
        "lqip": lqip,
        "largest": max(by_width.values(), key=lambda a: a.width) if by_width else asset,
    }
