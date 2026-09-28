"""Contact messages: an inbound queue for the artist."""

from __future__ import annotations

from django.db import models

from apps.core.models import TimeStampedModel


class ContactMessage(TimeStampedModel):
    name = models.CharField(max_length=160)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    subject = models.CharField(max_length=160, blank=True)
    message = models.TextField()

    is_read = models.BooleanField(default=False, db_index=True)
    replied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["is_read", "-created_at"])]

    def __str__(self):
        return f"{self.name} — {self.subject or 'no subject'}"
