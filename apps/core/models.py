"""
Core models: shared abstract bases and site-wide singletons.

This module is the foundation every other app builds on, so it deliberately depends on
nothing. See docs/erd.md section 1 and docs/django-apps.md for the full rationale.
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


# ======================================================================================
# Abstract bases
# ======================================================================================
class TimeStampedModel(models.Model):
    """Every model in the project inherits this."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class PublishableModel(TimeStampedModel):
    """
    Content with a public page.

    Uses ``status`` + ``published_at`` rather than a lone ``is_published`` boolean so
    that scheduled publishing is possible later without a migration.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        abstract = True

    def publish(self) -> None:
        self.status = self.Status.PUBLISHED
        self.published_at = self.published_at or timezone.now()
        self.save(update_fields=["status", "published_at", "updated_at"])


class SEOMixin(models.Model):
    """Optional per-object SEO overrides, with a documented fallback chain."""

    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.CharField(max_length=320, blank=True)

    class Meta:
        abstract = True

    def get_meta_title(self, fallback: str = "") -> str:
        return self.meta_title or fallback

    def get_meta_description(self, fallback: str = "") -> str:
        return self.meta_description or fallback


class SingletonModel(models.Model):
    """
    A model with exactly one row, enforced at the database level.

    ``load()`` creates the row on first access so templates never have to guard against
    a missing SiteSettings -- which would otherwise 500 every page on a fresh install.
    """

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """
        Force pk=1 so a singleton can never acquire a second row.

        Implementation note: writing ``self.pk = 1`` and calling super().save() is not
        sufficient. Django infers INSERT vs UPDATE from whether the pk is populated, so
        assigning it makes a first save look like an UPDATE against a row that does not
        exist -- which quietly affects zero rows and leaves the table empty.

        Forcing the insert instead is also wrong: ``force_insert=True`` bypasses the
        pre_save hook that populates ``auto_now_add`` fields, so ``created_at`` inserts
        as NULL and the not-null constraint rejects it.

        The reliable path is to supply the timestamps ourselves and pin only the pk, so
        Django's own insert logic still runs (including the hooks for other fields).
        """
        self.pk = 1
        now = timezone.now()
        for field in self._meta.fields:
            if (getattr(field, "auto_now_add", False) and getattr(self, field.attname) is None) or getattr(field, "auto_now", False):
                setattr(self, field.attname, now)

        if self.__class__.objects.filter(pk=1).exists():
            kwargs["force_update"] = True
        else:
            kwargs["force_insert"] = True
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Singleton rows cannot be deleted.")

    @classmethod
    def load(cls):
        return cls.objects.get_or_create(pk=1)[0]


class PublishedManager(models.Manager):
    """
    Exposes ``.published()`` so no view writes the publication filter by hand.

    The `published_at` condition is: null OR in the past.

    Requiring a non-null timestamp would mean an editor who sets status=published but
    leaves the date blank sees their work silently vanish from the site — a confusing
    failure with no error message. Treating a blank date as "published immediately" is
    both the intuitive behaviour and the safe one, because the status field is still the
    gate: a draft is never shown regardless of its date.
    """

    def published(self):
        now = timezone.now()
        return self.get_queryset().filter(
            status=PublishableModel.Status.PUBLISHED,
        ).filter(
            models.Q(published_at__isnull=True) | models.Q(published_at__lte=now)
        )


# ======================================================================================
# Uploads
# ======================================================================================
def media_upload_path(instance: MediaAsset, filename: str) -> str:
    """
    Store uploads under a UUID name, partitioned by date.

    Never trust or reuse the client's filename: it may contain path traversal, unicode
    tricks, or a dangerous extension. The original extension is preserved only after it
    has been validated against an allow-list.
    """
    ext = Path(filename).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}:
        ext = ".bin"
    # No leading "media/" -- MEDIA_ROOT already points at the media directory, so
    # including it again produced media/media/2026/...
    return f"{timezone.now():%Y/%m}/{uuid.uuid4().hex}{ext}"


class MediaAsset(TimeStampedModel):
    """
    The single upload abstraction for the whole project.

    Content models never hold a bare ``ImageField``; they point at a MediaAsset. That is
    what makes image derivatives, the halftone/dither sibling, deduplication and alt-text
    management exist in exactly one place.
    """

    class Kind(models.TextChoices):
        ORIGINAL = "original", "Original"
        DERIVATIVE = "derivative", "Derivative"
        DITHER = "dither", "Dither"
        LQIP = "lqip", "Low-quality placeholder"

    file = models.ImageField(upload_to=media_upload_path, max_length=255)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.ORIGINAL, db_index=True)
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    byte_size = models.PositiveIntegerField(default=0)
    sha256 = models.CharField(
        max_length=64,
        db_index=True,
        blank=True,
        help_text="Content hash of the ORIGINAL file. Shared by all variants of one image.",
    )
    variant_key = models.CharField(
        max_length=40,
        blank=True,
        db_index=True,
        help_text=(
            "Distinguishes variants of the same source image: '' for the original, "
            "the width for a derivative, 'dither' / 'lqip' for those plates."
        ),
    )
    alt_text = models.CharField(
        max_length=200,
        blank=True,
        help_text="Describe the image for screen readers and search engines.",
    )

    # --- Per-image dither control -------------------------------------------
    # The halftone threshold is NOT a global constant. High-key paper-ground engraving
    # needs a low threshold to keep thin lines legible; a dark-ground piece needs a high
    # one or it crushes into a solid block. Measured and documented in
    # docs/art-direction.md -- this is why it is a per-asset field.
    dither_threshold = models.PositiveSmallIntegerField(
        default=118,
        help_text=(
            "Halftone cutoff (0-255). Lower = denser dots, keeps fine lines. "
            "Higher = sparser, protects dark artwork from crushing. Default 118."
        ),
    )
    dither_width = models.PositiveSmallIntegerField(
        default=1600,
        help_text="Working width for dither plate generation.",
    )

    class Meta:
        verbose_name = "media asset"
        verbose_name_plural = "media assets"
        constraints = [
            # One asset per (source content, variant). Using variant_key rather than
            # overloading sha256 keeps the hash a pure content identifier and avoids
            # exceeding the 64-char digest column.
            models.UniqueConstraint(
                fields=["sha256", "kind", "variant_key"], name="uniq_asset_sha_kind_variant"
            ),
        ]
        indexes = [models.Index(fields=["kind", "created_at"])]

    def __str__(self) -> str:
        name = self.alt_text or Path(self.file.name).name
        return f"{name} ({self.width}x{self.height})"

    @property
    def aspect_ratio(self) -> float:
        return (self.width / self.height) if self.height else 1.0

    def compute_sha256(self) -> str:
        h = hashlib.sha256()
        self.file.open("rb")
        try:
            for chunk in iter(lambda: self.file.read(65536), b""):
                h.update(chunk)
        finally:
            self.file.close()
        return h.hexdigest()


# ======================================================================================
# Taxonomy
# ======================================================================================
class Tag(TimeStampedModel):
    """
    Shared across tattoos, artworks, products and clients.

    ``kind`` scopes the namespace so a tattoo tag and a product tag may share a slug
    without colliding.
    """

    class Kind(models.TextChoices):
        TATTOO = "tattoo", "Tattoo"
        ARTWORK = "artwork", "Artwork"
        PRODUCT = "product", "Product"
        CLIENT = "client", "Client"

    name = models.CharField(max_length=60)
    slug = models.SlugField(max_length=70, db_index=True)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.TATTOO, db_index=True)

    class Meta:
        ordering = ["kind", "name"]
        constraints = [
            models.UniqueConstraint(fields=["slug", "kind"], name="uniq_tag_slug_kind"),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


# ======================================================================================
# Site-wide singletons
# ======================================================================================
class SiteSettings(SingletonModel, TimeStampedModel):
    """
    Homepage and site-wide content, fully CMS-editable.

    Nothing important is hard-coded in a template: hero copy, contact details, the
    booking switch and the announcement all live here.
    """

    site_name = models.CharField(max_length=120, default="TattoWeb")
    tagline = models.CharField(max_length=200, blank=True)

    hero_kicker = models.CharField(
        max_length=120,
        blank=True,
        default="TATTOO ARTIST / VISUAL ARTIST",
        help_text="Small mono line above the hero headline.",
    )
    hero_title = models.CharField(
        max_length=200,
        blank=True,
        default="ART THAT MOVES WITH YOU",
        help_text="The oversized headline. Line breaks are respected.",
    )
    hero_media = models.ForeignKey(
        MediaAsset,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    default_meta_description = models.CharField(max_length=320, blank=True)
    og_default_image = models.ForeignKey(
        MediaAsset,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=40, blank=True)
    studio_address = models.TextField(blank=True)
    map_embed_url = models.URLField(blank=True)

    booking_open = models.BooleanField(
        default=True, help_text="Master switch for the booking form."
    )
    announcement = models.TextField(
        blank=True, help_text="Optional studio notice shown site-wide."
    )

    class Meta:
        verbose_name = "site settings"
        verbose_name_plural = "site settings"

    def __str__(self) -> str:
        return self.site_name

    @property
    def hero_lines(self) -> list[str]:
        """Hero headline split for the per-line masked reveal."""
        if not self.hero_title:
            return []
        return [line.strip() for line in self.hero_title.splitlines() if line.strip()]


class SocialLink(TimeStampedModel):
    """Artist social profiles, ordered, CMS-managed."""

    class Platform(models.TextChoices):
        INSTAGRAM = "instagram", "Instagram"
        TELEGRAM = "telegram", "Telegram"
        EMAIL = "email", "Email"
        BEHANCE = "behance", "Behance"
        X = "x", "X / Twitter"
        WEBSITE = "website", "Website"

    platform = models.CharField(max_length=40, choices=Platform.choices)
    label = models.CharField(max_length=80, help_text="Display text, e.g. @artist")
    url = models.URLField(blank=True)
    handle = models.CharField(max_length=80, blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "label"]
        indexes = [models.Index(fields=["is_active", "order"])]

    def __str__(self) -> str:
        return f"{self.get_platform_display()} — {self.label}"
