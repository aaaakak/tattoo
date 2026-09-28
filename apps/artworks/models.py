"""
Artwork models: paintings, drawings, illustration, digital, prints, experimental.

Deliberately NOT a tattoo category (docs/erd.md section 4). Different fields -- medium,
dimensions, year, edition -- and a different presentation: a gallery object rather than a
body-placement record.
"""

from __future__ import annotations

from django.db import models
from django.utils.text import slugify

from apps.core.models import (
    MediaAsset,
    PublishableModel,
    PublishedManager,
    SEOMixin,
    TimeStampedModel,
)


class ArtworkCategory(TimeStampedModel, SEOMixin):
    """Paintings / Drawings / Illustration / Digital / Prints / Experimental -- CMS-managed."""

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True, db_index=True)
    description = models.TextField(blank=True)
    cover = models.ForeignKey(
        MediaAsset, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    is_featured = models.BooleanField(default=False, db_index=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "artwork categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        # super().save() is REQUIRED. Without it the object is never written: the method
        # generates a slug and returns, leaving pk as None. That is silent data loss --
        # no exception, no error, just a row that does not exist.
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        from django.urls import reverse

        return reverse("artworks:category", kwargs={"slug": self.slug})


class Artwork(PublishableModel, SEOMixin):
    """A single artwork. Category is PROTECTed -- no orphaned art."""

    class Availability(models.TextChoices):
        AVAILABLE = "available", "Available"
        SOLD = "sold", "Sold"
        COMMISSION = "commission", "Commission"
        PRIVATE = "private", "Private collection"

    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True, db_index=True)
    description = models.TextField(blank=True)

    category = models.ForeignKey(
        ArtworkCategory, on_delete=models.PROTECT, related_name="artworks"
    )

    medium = models.CharField(max_length=120, blank=True, help_text='e.g. "Ink on paper".')
    dimensions = models.CharField(max_length=80, blank=True, help_text='e.g. "70 x 100 cm".')
    year = models.PositiveSmallIntegerField(null=True, blank=True, db_index=True)

    availability = models.CharField(
        max_length=20, choices=Availability.choices,
        default=Availability.AVAILABLE, db_index=True,
    )
    price = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="EUR")
    edition_info = models.CharField(max_length=120, blank=True, help_text='e.g. "Ed. 2/25".')

    is_featured = models.BooleanField(default=False, db_index=True)

    # See Tattoo.is_placeholder -- demonstration content must be visibly distinguishable.
    is_placeholder = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Demonstration content. Displayed with a visible notice on the site.",
    )
    tags = models.ManyToManyField("core.Tag", blank=True, related_name="artworks")

    objects = PublishedManager()

    class Meta:
        ordering = ["-year", "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price__isnull=True) | models.Q(price__gte=0),
                name="artwork_price_non_negative",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "is_featured", "-year"]),
            models.Index(fields=["category", "status"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    @property
    def primary_image(self):
        return self.images.filter(is_primary=True).first() or self.images.first()

    def get_absolute_url(self) -> str:
        from django.urls import reverse

        return reverse("artworks:detail", kwargs={"slug": self.slug})


class ArtworkImage(TimeStampedModel):
    """Same shape as TattooImage -- one pattern, applied consistently."""

    artwork = models.ForeignKey(Artwork, on_delete=models.CASCADE, related_name="images")
    asset = models.ForeignKey(
        MediaAsset, on_delete=models.PROTECT, related_name="artwork_images"
    )
    caption = models.CharField(max_length=200, blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["artwork", "order"], name="uniq_artworkimage_order"),
            models.UniqueConstraint(
                fields=["artwork"], condition=models.Q(is_primary=True),
                name="uniq_artwork_primary_image",
            ),
        ]

    def __str__(self):
        return self.caption or f"Image {self.order} of {self.artwork.title}"
