"""
Booking models: availability, blocked dates, requests, references and appointments.

The hardest correctness requirement in the project lives here: double-booking must be
IMPOSSIBLE, not merely unlikely. That is enforced by a Postgres EXCLUDE constraint on
Appointment (see migration 0002 and docs/erd.md section 7). Application-level checks give
friendly errors; the database constraint gives truth under concurrency.
"""

from __future__ import annotations

import secrets

from django.db import models

from apps.core.models import MediaAsset, TimeStampedModel

# Unambiguous alphabet for reference codes -- no 0/O/1/I, so a client can read it aloud.
_REF_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def generate_reference() -> str:
    body = "".join(secrets.choice(_REF_ALPHABET) for _ in range(6))
    return f"TW-{body}"


class Availability(TimeStampedModel):
    """Recurring weekly working template."""

    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_minutes = models.PositiveSmallIntegerField(default=60)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["weekday", "start_time"]
        verbose_name_plural = "availability"
        constraints = [
            models.UniqueConstraint(fields=["weekday", "start_time"], name="uniq_availability_slot"),
            models.CheckConstraint(condition=models.Q(end_time__gt=models.F("start_time")),
                                   name="availability_end_after_start"),
        ]

    def __str__(self):
        return f"{self.get_weekday_display()} {self.start_time:%H:%M}-{self.end_time:%H:%M}"


class BlockedDate(TimeStampedModel):
    """A specific date or range the artist is unavailable."""

    date = models.DateField(db_index=True)
    end_date = models.DateField(null=True, blank=True, help_text="Optional inclusive range end.")
    reason = models.CharField(max_length=160, blank=True)
    all_day = models.BooleanField(default=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)

    class Meta:
        ordering = ["date"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__isnull=True) | models.Q(end_date__gte=models.F("date")),
                name="blockeddate_end_after_start",
            ),
        ]
        indexes = [models.Index(fields=["date"]), models.Index(fields=["date", "end_date"])]

    def __str__(self):
        if self.end_date and self.end_date != self.date:
            return f"Blocked {self.date} to {self.end_date}"
        return f"Blocked {self.date}"


class Booking(TimeStampedModel):
    """A client's tattoo request, with a real workflow."""

    class Status(models.TextChoices):
        NEW = "new", "New"
        REVIEWING = "reviewing", "Reviewing"
        POTENTIAL = "potential", "Potential client"
        APPROVED = "approved", "Approved"
        SCHEDULED = "scheduled", "Scheduled"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        REJECTED = "rejected", "Rejected"

    class ColorChoice(models.TextChoices):
        COLOR = "color", "Colour"
        BLACK_GREY = "black_grey", "Black & grey"
        UNDECIDED = "undecided", "Undecided"

    reference = models.CharField(max_length=12, unique=True, db_index=True, default=generate_reference)

    client = models.ForeignKey(
        "clients.Client", on_delete=models.PROTECT, related_name="bookings"
    )
    style = models.ForeignKey(
        "tattoos.TattooStyle", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="bookings",
    )

    placement = models.CharField(max_length=80, blank=True)
    approx_size = models.CharField(max_length=40, blank=True)
    is_color = models.CharField(max_length=10, choices=ColorChoice.choices,
                                default=ColorChoice.UNDECIDED)
    description = models.TextField()

    budget_min = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    budget_max = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices,
                              default=Status.NEW, db_index=True)
    preferred_date = models.DateField(null=True, blank=True, db_index=True)
    preferred_time = models.CharField(max_length=20, blank=True)

    internal_notes = models.TextField(blank=True)
    contact_consent = models.BooleanField(default=False)
    source = models.CharField(max_length=20, default="web")

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(budget_max__isnull=True)
                | models.Q(budget_min__isnull=True)
                | models.Q(budget_max__gte=models.F("budget_min")),
                name="booking_budget_range_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["preferred_date"]),
            models.Index(fields=["client"]),
        ]

    def __str__(self):
        return f"{self.reference} — {self.client.name} ({self.get_status_display()})"

    @property
    def open_statuses(self):
        return {self.Status.NEW, self.Status.REVIEWING, self.Status.POTENTIAL,
                self.Status.APPROVED, self.Status.SCHEDULED}


class BookingReference(TimeStampedModel):
    """A reference image uploaded with a booking. Max 8 enforced at service level."""

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="references")
    asset = models.ForeignKey(MediaAsset, on_delete=models.PROTECT, related_name="booking_references")
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["booking"])]

    def __str__(self):
        return self.note or f"Reference for {self.booking.reference}"


class Appointment(TimeStampedModel):
    """
    A scheduled session.

    The EXCLUDE USING gist (tsrange(start_at, end_at) WITH &&) constraint added in the
    migration makes overlapping scheduled appointments impossible at the database level.
    """

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        CONFIRMED = "confirmed", "Confirmed"
        DONE = "done", "Done"
        NO_SHOW = "no_show", "No show"
        CANCELLED = "cancelled", "Cancelled"

    booking = models.OneToOneField(
        Booking, null=True, blank=True, on_delete=models.SET_NULL, related_name="appointment"
    )
    client = models.ForeignKey(
        "clients.Client", on_delete=models.PROTECT, related_name="appointments"
    )
    start_at = models.DateTimeField(db_index=True)
    end_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices,
                              default=Status.SCHEDULED, db_index=True)
    calendar_event_id = models.CharField(
        max_length=200, blank=True,
        help_text="Reserved for a future Google Calendar sync. Unused today.",
    )
    internal_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["start_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(end_at__gt=models.F("start_at")),
                                   name="appointment_end_after_start"),
        ]
        indexes = [models.Index(fields=["start_at"]), models.Index(fields=["status", "start_at"])]

    def __str__(self):
        return f"{self.client.name} @ {self.start_at:%Y-%m-%d %H:%M}"
