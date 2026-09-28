"""
Artist models: the identity layer consumed by every page.

Placeholder values are seeded via a management command so the site renders realistically
before real information exists; everything here is replaceable from the Django admin.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import MediaAsset, SingletonModel, TimeStampedModel


class ArtistProfile(SingletonModel, TimeStampedModel):
    """
    The artist's public identity. Singleton.

    Every field is a placeholder by default -- the site is built so the artist replaces
    them through the admin rather than through code.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="artist_profile",
        help_text="Optional login link for the artist.",
    )

    display_name = models.CharField(max_length=120, default="STUDIO NAME")
    monogram = models.CharField(
        max_length=6,
        default="TW",
        help_text="Short mark shown in the header, e.g. two or three characters.",
    )
    role_line = models.CharField(
        max_length=160, default="TATTOO ARTIST / VISUAL ARTIST"
    )

    statement = models.TextField(
        blank=True,
        default="INK IS ONLY THE MEDIUM.",
        help_text="The artist's statement. Rendered as an editorial headline.",
    )
    biography = models.TextField(
        blank=True,
        help_text="Long-form biography. Blank lines become paragraphs.",
    )

    portrait = models.ForeignKey(
        MediaAsset,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    location_city = models.CharField(max_length=80, blank=True)
    location_country = models.CharField(max_length=80, blank=True)
    years_experience = models.PositiveSmallIntegerField(default=0)

    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)

    is_booking_open = models.BooleanField(
        default=True, help_text="Second booking switch; both this and SiteSettings must be on."
    )

    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.CharField(max_length=320, blank=True)

    class Meta:
        verbose_name = "artist profile"
        verbose_name_plural = "artist profile"

    def __str__(self) -> str:
        return self.display_name

    @property
    def location(self) -> str:
        parts = [p for p in (self.location_city, self.location_country) if p]
        return ", ".join(parts)

    @property
    def biography_paragraphs(self) -> list[str]:
        if not self.biography:
            return []
        return [p.strip() for p in self.biography.split("\n\n") if p.strip()]


class Statistic(TimeStampedModel):
    """
    The 10+ / 1200+ / 08 / 01 block.

    ``value`` is stored as text rather than an integer so that "10+" and "08" render
    exactly as the artist intends -- leading zeros and suffixes are part of the design.
    """

    artist = models.ForeignKey(
        ArtistProfile,
        on_delete=models.CASCADE,
        related_name="statistics",
    )
    value = models.CharField(max_length=20, help_text='e.g. "10+", "1200+", "08"')
    label = models.CharField(max_length=60, help_text='e.g. "YEARS", "TATTOOS"')
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(fields=["artist", "order"], name="uniq_statistic_order"),
        ]
        indexes = [models.Index(fields=["artist", "order"])]

    def __str__(self) -> str:
        return f"{self.value} {self.label}"
