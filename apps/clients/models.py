"""
Client models: a light internal record, not a CRM.

Deleting a client is PROTECTed while bookings exist -- the artist archives history,
never erases it. See docs/erd.md section 6.
"""

from __future__ import annotations

from django.db import models
from django.utils.text import slugify

from apps.core.models import TimeStampedModel


class Client(TimeStampedModel):
    name = models.CharField(max_length=160, db_index=True)
    slug = models.SlugField(max_length=180, unique=True, db_index=True)
    email = models.EmailField(blank=True, db_index=True)
    phone = models.CharField(max_length=40, blank=True)
    instagram = models.CharField(max_length=80, blank=True)
    telegram = models.CharField(max_length=80, blank=True)

    notes = models.TextField(blank=True, help_text="Private artist notes.")
    preferences = models.TextField(blank=True)
    is_vip = models.BooleanField(default=False)

    tags = models.ManyToManyField("core.Tag", blank=True, related_name="clients")

    class Meta:
        ordering = ["name"]
        constraints = [
            # A real email identifies a client; empty strings do not collide.
            models.UniqueConstraint(
                fields=["email"],
                condition=~models.Q(email=""),
                name="uniq_client_email_nonempty",
            ),
        ]
        indexes = [models.Index(fields=["name"]), models.Index(fields=["email"])]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or "client"
            candidate, n = base_slug, 2
            while Client.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base_slug}-{n}"
                n += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    @property
    def booking_count(self) -> int:
        return self.bookings.count()
