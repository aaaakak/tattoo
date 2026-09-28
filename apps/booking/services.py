"""
Booking services — orchestration that does not belong in a view or a serializer.

The availability *rules* live in services/availability.py (framework-free, shared with
FastAPI). Everything here is Django-side orchestration: reading rows, calling the engine,
and writing the result in one transaction.

Both the HTML form and the FastAPI endpoint call `create_booking_from_payload`, so the
two paths cannot drift.
"""

from __future__ import annotations

import logging
from datetime import date as date_cls
from datetime import datetime, time, timedelta

from django.db import transaction
from django.utils import timezone

from services import availability as engine

from .models import Appointment, Availability, BlockedDate, Booking, BookingReference

logger = logging.getLogger("apps")

# A booking request is refused beyond this horizon: dates far in the future are usually
# speculative and clutter the queue.
MAX_ADVANCE_DAYS = 365


class BookingError(Exception):
    """Raised when a booking cannot be created. Message is safe to show a user."""


# --------------------------------------------------------------------------------------
# Loading engine inputs
# --------------------------------------------------------------------------------------
def load_availability() -> list[engine.AvalRow]:
    return [
        engine.AvalRow(
            weekday=a.weekday,
            start_time=a.start_time,
            end_time=a.end_time,
            slot_minutes=a.slot_minutes,
            is_active=a.is_active,
        )
        for a in Availability.objects.all()
    ]


def load_blocked(start: date_cls, end: date_cls) -> list[engine.BlockedRow]:
    """
    Blocked rows overlapping the requested window.

    The filter is inclusive on both sides: a range that *starts* before the window but
    extends into it still blocks, so the overlap condition is (date <= end AND
    COALESCE(end_date, date) >= start).
    """
    from django.db.models import Q

    rows = BlockedDate.objects.filter(
        Q(date__lte=end) & (Q(end_date__gte=start) | Q(end_date__isnull=True, date__gte=start))
    )
    return [
        engine.BlockedRow(
            date=b.date,
            end_date=b.end_date,
            all_day=b.all_day,
            start_time=b.start_time,
            end_time=b.end_time,
        )
        for b in rows
    ]


def load_booked(start: date_cls, end: date_cls) -> list[engine.ApptRow]:
    start_dt = timezone.make_aware(datetime.combine(start, time.min))
    end_dt = timezone.make_aware(datetime.combine(end, time.max))
    rows = Appointment.objects.filter(start_at__lt=end_dt, end_at__gt=start_dt)
    return [
        engine.ApptRow(start_at=a.start_at, end_at=a.end_at, status=a.status)
        for a in rows
    ]


# --------------------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------------------
def slots_for_day(day: date_cls) -> list[engine.Slot]:
    """
    Every slot for one day with its availability state.

    The active timezone is passed explicitly so the engine's naive date/time inputs are
    made aware before any comparison with `now` or with stored appointments.
    """
    now = timezone.localtime()
    return engine.compute_slots(
        day=day,
        availability=load_availability(),
        blocked=load_blocked(day, day),
        booked=load_booked(day, day),
        now=now,
        tz=timezone.get_current_timezone(),
    )


def open_days_for_month(year: int, month: int) -> list[date_cls]:
    """Which dates in a month have any bookable slot. Drives the calendar widget."""
    first = date_cls(year, month, 1)
    next_month = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    last = next_month - timedelta(days=1)

    now = timezone.localtime()
    return engine.available_days(
        start=first,
        end=last,
        availability=load_availability(),
        blocked=load_blocked(first, last),
        booked=load_booked(first, last),
        now=now,
        tz=timezone.get_current_timezone(),
    )


def next_open_days(count: int = 3) -> list[date_cls]:
    """The next few bookable dates, for the homepage availability line."""
    today = timezone.localdate()
    horizon = today + timedelta(days=90)
    now = timezone.localtime()
    days = engine.available_days(
        start=today,
        end=horizon,
        availability=load_availability(),
        blocked=load_blocked(today, horizon),
        booked=load_booked(today, horizon),
        now=now,
        tz=timezone.get_current_timezone(),
    )
    return days[:count]


# --------------------------------------------------------------------------------------
# Creation
# --------------------------------------------------------------------------------------
@transaction.atomic
def create_booking_from_payload(payload: dict, files: list | None = None) -> Booking:
    """
    Create a Client (or reuse one by email), a Booking, and its reference images.

    Shared by the Django form and the FastAPI endpoint. Raises BookingError with a
    user-safe message; never leaks an internal exception.

    The Client is PROTECTed by the Booking FK, so a returning client accumulates history
    rather than being duplicated — matched on email, which is the only reliable key.
    """
    from apps.clients.models import Client
    from apps.core.ingest import UploadValidationError, ingest_image

    files = files or []

    email = (payload.get("email") or "").strip()
    name = (payload.get("name") or "").strip()
    if not name:
        raise BookingError("A name is required.")
    if not email:
        raise BookingError("An email address is required so the studio can reply.")

    description = (payload.get("description") or "").strip()
    if len(description) < 10:
        raise BookingError("Please describe the idea in a little more detail.")

    preferred_date = payload.get("preferred_date")
    if preferred_date:
        today = timezone.localdate()
        if preferred_date < today:
            raise BookingError("The preferred date is in the past.")
        if preferred_date > today + timedelta(days=MAX_ADVANCE_DAYS):
            raise BookingError("Please choose a date within the next year.")

        # Only refuse when the artist actually has availability configured; an empty
        # Availability table means "not yet set up", not "closed forever".
        if Availability.objects.filter(is_active=True).exists():
            open_days = open_days_for_month(preferred_date.year, preferred_date.month)
            if preferred_date not in open_days:
                raise BookingError(
                    "That date has no availability. Please choose another, "
                    "or leave it open and the studio will suggest times."
                )

    client, created = Client.objects.get_or_create(
        email=email,
        defaults={
            "name": name,
            "phone": (payload.get("phone") or "").strip(),
            "instagram": (payload.get("instagram") or "").strip(),
            "telegram": (payload.get("telegram") or "").strip(),
        },
    )
    if not created:
        # Keep contact details current without clobbering the artist's own notes.
        changed = []
        for field in ("phone", "instagram", "telegram"):
            value = (payload.get(field) or "").strip()
            if value and getattr(client, field) != value:
                setattr(client, field, value)
                changed.append(field)
        if changed:
            client.save(update_fields=changed)

    style = payload.get("style")
    booking = Booking.objects.create(
        client=client,
        style=style if style and hasattr(style, "pk") else None,
        placement=(payload.get("placement") or "").strip(),
        approx_size=(payload.get("approx_size") or "").strip(),
        is_color=payload.get("is_color") or Booking.ColorChoice.UNDECIDED,
        description=description,
        budget_min=payload.get("budget_min"),
        budget_max=payload.get("budget_max"),
        preferred_date=preferred_date,
        preferred_time=(payload.get("preferred_time") or "").strip(),
        contact_consent=bool(payload.get("contact_consent")),
        source=payload.get("source") or "web",
        status=Booking.Status.NEW,
    )

    for uploaded in files:
        try:
            uploaded.seek(0)
            content = uploaded.read()
            asset = ingest_image(
                filename=f"bookings/{uploaded.name}",
                content=content,
                alt_text=f"Reference image for {booking.reference}",
            )
        except UploadValidationError as exc:
            # One bad file must not lose the whole request: log it, skip it, keep going.
            logger.warning("booking %s: rejected reference %s: %s", booking.reference, uploaded.name, exc)
            continue
        BookingReference.objects.create(booking=booking, asset=asset, note=uploaded.name[:200])

    logger.info("booking created: %s for %s", booking.reference, client.name)
    return booking


def notify_new_booking(booking: Booking) -> bool:
    """
    Notify the artist of a new request.

    Returns True when an email was actually sent. With no EMAIL_HOST configured (the
    default in development), this logs instead of pretending to send — a booking must
    never be silently lost because mail was misconfigured.
    """
    from django.conf import settings
    from django.core.mail import send_mail

    recipient = None
    try:
        from apps.core.models import SiteSettings

        recipient = SiteSettings.load().contact_email
    except Exception:
        recipient = None

    if not recipient:
        logger.warning("booking %s: no contact_email configured, notification skipped", booking.reference)
        return False

    if not settings.EMAIL_HOST:
        logger.info(
            "booking %s received (no SMTP configured; not emailed): %s / %s",
            booking.reference, booking.client.name, booking.client.email,
        )
        return False

    try:
        send_mail(
            subject=f"New booking request {booking.reference}",
            message=(
                f"From: {booking.client.name} <{booking.client.email}>\n"
                f"Style: {booking.style.name if booking.style else '-'}\n"
                f"Placement: {booking.placement or '-'}\n"
                f"Size: {booking.approx_size or '-'}\n"
                f"Preferred: {booking.preferred_date or '-'} {booking.preferred_time or ''}\n"
                f"References: {booking.references.count()}\n\n"
                f"{booking.description}\n"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
        return True
    except Exception:
        logger.exception("booking %s: notification email failed", booking.reference)
        return False
