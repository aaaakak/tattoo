"""
Gallery models: a CURATION layer over existing media, not a third content type.

GalleryImage references TattooImage or ArtworkImage through nullable one-to-one links and
carries its own layout metadata (aspect, span, order). Putting layout concerns on
TattooImage would leak gallery interests into the tattoo domain. See docs/erd.md section 5.
"""

from __future__ import annotations

from django.db import models
from django.utils.text import slugify

from apps.artworks.models import ArtworkImage
from apps.core.models import MediaAsset, SEOMixin, TimeStampedModel
from apps.tattoos.models import TattooImage


class GalleryCollection(TimeStampedModel, SEOMixin):
    """A curated set, e.g. "INK STUDIES" or "2026 SELECTED"."""

    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True, db_index=True)
    description = models.TextField(blank=True)
    cover = models.ForeignKey(
        MediaAsset, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    is_featured = models.BooleanField(default=False, db_index=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "title"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class GalleryImage(TimeStampedModel):
    """
    A single gallery entry.

    ``aspect`` is stored explicitly so the masonry layout can be computed without
    measuring images at runtime -- this is what keeps the gallery free of layout shift.
    """

    class Aspect(models.TextChoices):
        PORTRAIT = "portrait", "Portrait"
        LANDSCAPE = "landscape", "Landscape"
        SQUARE = "square", "Square"

    collection = models.ForeignKey(
        GalleryCollection, null=True, blank=True,
        on_delete=models.CASCADE, related_name="images",
    )
    asset = models.ForeignKey(
        MediaAsset, on_delete=models.PROTECT, related_name="gallery_images"
    )

    # Optional provenance: where this gallery image originally came from.
    tattoo_image = models.OneToOneField(
        TattooImage, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    artwork_image = models.OneToOneField(
        ArtworkImage, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    caption = models.CharField(max_length=200, blank=True)
    aspect = models.CharField(max_length=10, choices=Aspect.choices, default=Aspect.PORTRAIT)
    span = models.PositiveSmallIntegerField(default=1, help_text="Grid span for asymmetry.")
    is_featured = models.BooleanField(default=False, db_index=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            # An image has ONE provenance, never two.
            models.CheckConstraint(
                condition=~(
                    models.Q(tattoo_image__isnull=False) & models.Q(artwork_image__isnull=False)
                ),
                name="gallery_image_single_provenance",
            ),
        ]
        indexes = [
            models.Index(fields=["collection", "order"]),
            models.Index(fields=["is_featured", "order"]),
        ]

    def __str__(self):
        return self.caption or f"Gallery image {self.pk}"
