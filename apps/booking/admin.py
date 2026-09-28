"""
Admin for the booking workflow: availability, blocked dates, bookings, appointments.

This is the most functionally important admin in the project — it is how the artist runs
their working life. Three things therefore get special care:

  1. Booking status is editable from the changelist, because triaging a queue is the
     actual daily task.
  2. Reference images are inline, so the artist sees what the client sent without
     leaving the page.
  3. Appointment creation surfaces the database's no-overlap constraint as a readable
     validation error rather than a 500.
"""

from __future__ import annotations

from django import forms
from django.contrib import admin
from django.db import IntegrityError, transaction
from django.utils.html import format_html

from .models import Appointment, Availability, BlockedDate, Booking, BookingReference


@admin.register(Availability)
class AvailabilityAdmin(admin.ModelAdmin):
    list_display = ("weekday", "start_time", "end_time", "slot_minutes", "is_active")
    list_filter = ("is_active", "weekday")
    list_editable = ("start_time", "end_time", "slot_minutes", "is_active")
    ordering = ("weekday", "start_time")

    fieldsets = (
        (
            "Working window",
            {
                "fields": ("weekday", "start_time", "end_time", "slot_minutes", "is_active"),
                "description": (
                    "The recurring weekly template. One row per working day. "
                    "Slot length controls how bookings are sliced."
                ),
            },
        ),
    )


@admin.register(BlockedDate)
class BlockedDateAdmin(admin.ModelAdmin):
    list_display = ("date", "end_date", "all_day", "reason")
    list_filter = ("all_day", "date")
    search_fields = ("reason",)
    date_hierarchy = "date"
    ordering = ("date",)

    fieldsets = (
        (
            "Blocked period",
            {
                "fields": ("date", "end_date", "all_day", "start_time", "end_time", "reason"),
                "description": (
                    "A single date, or a range when end_date is set. Partial-day blocks "
                    "use all_day=False with a time range."
                ),
            },
        ),
    )


class BookingReferenceInline(admin.TabularInline):
    """Client-supplied reference images, shown as thumbnails."""

    model = BookingReference
    extra = 0
    autocomplete_fields = ("asset",)
    fields = ("asset", "thumbnail", "note")
    readonly_fields = ("thumbnail",)

    @admin.display(description="preview")
    def thumbnail(self, obj):
        if not obj.asset or not obj.asset.file:
            return "—"
        return format_html(
            '<img src="{}" style="height:80px;border:1px solid #333;background:#111">',
            obj.asset.file.url,
        )


class AppointmentInline(admin.StackedInline):
    """
    The appointment attached to a booking.

    Overlap validation is delegated to the database: the EXCLUDE constraint on
    booking_appointment makes double-booking impossible, and this inline translates the
    resulting IntegrityError into a readable form error instead of a 500.
    """

    model = Appointment
    extra = 0
    max_num = 1
    autocomplete_fields = ("client",)
    fields = ("client", "start_at", "end_at", "status", "calendar_event_id", "internal_notes")

    def save_formset(self, request, form, formset, change):
        try:
            with transaction.atomic():
                super().save_formset(request, form, formset, change)
        except IntegrityError as exc:
            if "appointment_no_overlap" in str(exc):
                raise forms.ValidationError(
                    "This appointment overlaps an existing scheduled session. "
                    "Choose a different time, or cancel the conflicting one first."
                ) from exc
            raise


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    # Both `status` (the raw field, required for list_editable) and `status_pill`
    # (the coloured rendering) appear in the changelist. Django requires the editable
    # field itself to be in list_display; the pill is presentation.
    list_display = (
        "reference", "client_name", "style", "placement", "status", "status_pill",
        "preferred_date", "created_at",
    )
    list_filter = ("status", "is_color", "source", "created_at", "style")
    search_fields = ("reference", "client__name", "client__email", "description", "placement")
    autocomplete_fields = ("client", "style")
    inlines = [BookingReferenceInline, AppointmentInline]
    readonly_fields = ("reference", "created_at", "updated_at", "reference_images_summary")
    date_hierarchy = "created_at"
    list_editable = ("status",)
    list_per_page = 30
    save_on_top = True

    fieldsets = (
        ("Request", {"fields": ("reference", "client", "status", "source", "contact_consent")}),
        ("The piece", {"fields": ("style", "placement", "approx_size", "is_color", "description")}),
        ("Budget", {"fields": ("budget_min", "budget_max")}),
        ("Timing preference", {"fields": ("preferred_date", "preferred_time")}),
        (
            "Internal",
            {
                "fields": ("internal_notes",),
                "description": "Never shown to the client. Excluded from every public API schema.",
            },
        ),
        ("References received", {"fields": ("reference_images_summary",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    # Status colours, kept to the palette: cobalt for in-flight, neutral for done.
    _STATUS_COLOUR = {
        "new": "#1B2CFF",
        "reviewing": "#8A8A93",
        "potential": "#8A8A93",
        "approved": "#4ADE80",
        "scheduled": "#4ADE80",
        "completed": "#4A4A52",
        "cancelled": "#4A4A52",
        "rejected": "#FF5A5A",
    }

    @admin.display(description="client")
    def client_name(self, obj):
        return obj.client.name

    @admin.display(description="status", ordering="status")
    def status_pill(self, obj):
        colour = self._STATUS_COLOUR.get(obj.status, "#8A8A93")
        return format_html(
            '<span style="border:1px solid {};color:{};padding:1px 6px;'
            'font-size:11px;letter-spacing:.1em;text-transform:uppercase">{}</span>',
            colour, colour, obj.get_status_display(),
        )

    @admin.display(description="reference images")
    def reference_images_summary(self, obj):
        if not obj.pk:
            return "Save the booking first."
        refs = obj.references.all()
        if not refs.exists():
            return "None uploaded."
        imgs = "".join(
            format_html('<img src="{}" style="height:110px;margin:2px;border:1px solid #333">', r.asset.file.url)
            for r in refs if r.asset and r.asset.file
        )
        return format_html("<div>{}</div>", format_html(imgs))


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("client", "start_at", "end_at", "duration", "status", "booking")
    list_filter = ("status", "start_at")
    search_fields = ("client__name", "booking__reference", "internal_notes")
    autocomplete_fields = ("client", "booking")
    date_hierarchy = "start_at"
    ordering = ("-start_at",)

    fieldsets = (
        ("Session", {"fields": ("client", "booking", "start_at", "end_at", "status")}),
        (
            "Calendar integration",
            {
                "fields": ("calendar_event_id",),
                "description": "Reserved for a future Google Calendar sync. Unused today.",
            },
        ),
        ("Notes", {"fields": ("internal_notes",)}),
    )

    @admin.display(description="duration")
    def duration(self, obj):
        if not (obj.start_at and obj.end_at):
            return "—"
        minutes = int((obj.end_at - obj.start_at).total_seconds() // 60)
        return f"{minutes} min"

    def save_model(self, request, obj, form, change):
        """
        Translate the no-overlap constraint into a readable form error.

        Without this, a double-booked appointment raises a raw IntegrityError and the
        artist sees a 500 page instead of "that slot is taken".
        """
        try:
            with transaction.atomic():
                super().save_model(request, obj, form, change)
        except IntegrityError as exc:
            if "appointment_no_overlap" in str(exc):
                raise forms.ValidationError(
                    "This appointment overlaps an existing scheduled session. "
                    "Choose a different time, or cancel the conflicting one first."
                ) from exc
            raise
