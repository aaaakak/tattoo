"""
Tattoo models: styles, pieces and their images.

See docs/erd.md section 3. Slides are generated only when empty -- never overwriting an
editor's custom slug, because changing a slug breaks indexed URLs.
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


class TattooStyle(TimeStampedModel, SEOMixin):
    """
    A tattoo style (Blackwork, Fine Line, Gothic...).

    Fully CMS-managed -- never hard-coded, so the artist can add a signature style
    without a deploy. This is also a real SEO surface ("blackwork tattoo").
    """

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
        indexes = [models.Index(fields=["is_featured", "order"])]

    def __str__(self) -> str:
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

        return reverse("styles:detail", kwargs={"slug": self.slug})


class Tattoo(PublishableModel, SEOMixin):
    """
    A tattooed piece in the portfolio.

    Styles are many-to-many: a single piece is often blackwork *and* ornamental, and
    forcing one style would misrepresent the work.
    """

    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True, db_index=True)
    description = models.TextField(blank=True)
    artist_notes = models.TextField(blank=True, help_text="Shown on the detail page.")

    styles = models.ManyToManyField(
        TattooStyle, blank=True, related_name="tattoos"
    )

    placement = models.CharField(
        max_length=80, blank=True, db_index=True,
        help_text='e.g. "Forearm", "Ribs", "Hand", "Back".'
    )
    size_cm = models.CharField(max_length=40, blank=True, help_text='e.g. "12 x 18 cm".')
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)

    price_from = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    price_to = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="EUR")

    is_color = models.BooleanField(default=False, help_text="Colour vs black & grey.")
    is_featured = models.BooleanField(default=False, db_index=True)
    session_date = models.DateField(null=True, blank=True)

    # Demonstration content must be distinguishable from real work. This flag is shown in
    # the admin and drives a visible caption on the public detail page, so generated
    # sample artwork can never be mistaken for a real tattoo performed by the artist.
    is_placeholder = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Demonstration content. Displayed with a visible notice on the site.",
    )

    tags = models.ManyToManyField("core.Tag", blank=True, related_name="tattoos")

    objects = PublishedManager()

    class Meta:
        ordering = ["-published_at", "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price_to__isnull=True)
                | models.Q(price_from__isnull=True)
                | models.Q(price_to__gte=models.F("price_from")),
                name="tattoo_price_range_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "is_featured", "-published_at"]),
            models.Index(fields=["placement"]),
        ]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    @property
    def primary_image(self):
        """The image flagged primary, falling back to the first ordered image."""
        return self.images.filter(is_primary=True).first() or self.images.first()

    @property
    def style_names(self) -> list[str]:
        return [s.name for s in self.styles.all()]

    def get_absolute_url(self) -> str:
        from django.urls import reverse

        return reverse("tattoos:detail", kwargs={"slug": self.slug})


class TattooImage(TimeStampedModel):
    """
    An image belonging to a tattoo.

    The asset is PROTECTed: a shared MediaAsset must never be destroyed while a live
    parent still references it.
    """

    class Variant(models.TextChoices):
        DETAIL = "detail", "Detail"
        HEALED = "healed", "Healed"
        PROCESS = "process", "Process"
        STUDIO = "studio", "Studio"

    tattoo = models.ForeignKey(Tattoo, on_delete=models.CASCADE, related_name="images")
    asset = models.ForeignKey(
        MediaAsset, on_delete=models.PROTECT, related_name="tattoo_images"
    )
    caption = models.CharField(max_length=200, blank=True)
    variant = models.CharField(
        max_length=20, choices=Variant.choices, default=Variant.DETAIL
    )
    order = models.PositiveSmallIntegerField(default=0)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["tattoo", "order"], name="uniq_tattooimage_order"),
            # Exactly one primary image per tattoo, enforced by the database.
            models.UniqueConstraint(
                fields=["tattoo"],
                condition=models.Q(is_primary=True),
                name="uniq_tattoo_primary_image",
            ),
        ]
        indexes = [models.Index(fields=["tattoo", "order"])]

    def __str__(self) -> str:
        return self.caption or f"Image {self.order} of {self.tattoo.title}"
