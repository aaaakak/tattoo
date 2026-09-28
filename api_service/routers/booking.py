"""
Booking, availability and contact endpoints.

CRITICAL: the availability logic is NOT reimplemented here. Both this router and the
Django views call `services.availability`, so the no-double-booking rule exists exactly
once. Likewise `POST /bookings` delegates to the Django service function that the HTML
form uses, which is why the two paths cannot diverge.

To call Django ORM code from FastAPI we initialise Django once at import and use the
`.objects` managers directly. That is deliberate: the alternative (reimplementing
availability, client lookup and image ingestion in SQLAlchemy) would create a second copy
of the business rules, which is precisely what the architecture forbids.
"""

from __future__ import annotations

import logging
from datetime import date as date_cls

import django
from django.apps import apps as django_apps
from fastapi import APIRouter, HTTPException, Request, status

from api_service.deps import booking_limiter, client_key, contact_limiter
from api_service.schemas.booking import (
    AvailabilityDayOut,
    AvailabilityDaysOut,
    BookingCreate,
    BookingCreated,
    BookingPublic,
    ContactCreate,
    SlotOut,
)

router = APIRouter()
logger = logging.getLogger("apps")


def _ensure_django() -> None:
    """
    Initialise Django exactly once.

    The API reads and writes the same database through Django's ORM, so Django must be
    set up before any model is touched. `django.setup()` is idempotent.
    """
    if not django_apps.ready:
        django.setup()


# --------------------------------------------------------------------------------------
# Availability (read-only)
# --------------------------------------------------------------------------------------
@router.get(
    "/availability",
    response_model=AvailabilityDaysOut,
    summary="Which days in a month have bookable slots",
)
def availability_days(
    year: int | None = None,
    month: int | None = None,
):
    _ensure_django()
    from django.utils import timezone

    from apps.booking.services import open_days_for_month

    today = timezone.localdate()
    year = year or today.year
    month = month or today.month
    if not (1 <= month <= 12) or not (2000 <= year <= 2100):
        raise HTTPException(status_code=422, detail="invalid year or month")

    days = open_days_for_month(year, month)
    return AvailabilityDaysOut(
        year=year, month=month, open_days=[d.isoformat() for d in days], count=len(days)
    )


@router.get(
    "/availability/{day}",
    response_model=AvailabilityDayOut,
    summary="Slots for a single date",
)
def availability_for_day(day: str):
    _ensure_django()
    from apps.booking.services import slots_for_day

    try:
        parsed = date_cls.fromisoformat(day)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="date must be ISO format (YYYY-MM-DD)"
        ) from exc

    slots = slots_for_day(parsed)
    return AvailabilityDayOut(
        date=parsed.isoformat(),
        slots=[
            SlotOut(start=s.start, end=s.end, available=s.available, reason=s.reason)
            for s in slots
        ],
        available_count=sum(1 for s in slots if s.available),
    )


# --------------------------------------------------------------------------------------
# Booking submission
# --------------------------------------------------------------------------------------
@router.post(
    "/bookings",
    response_model=BookingCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a booking request",
)
def create_booking(payload: BookingCreate, request: Request):
    _ensure_django()
    booking_limiter.check(client_key(request), request)

    from apps.booking.services import BookingError, create_booking_from_payload, notify_new_booking
    from apps.tattoos.models import TattooStyle

    style = None
    if payload.style_slug:
        style = TattooStyle.objects.filter(slug=payload.style_slug).first()

    preferred = None
    if payload.preferred_date:
        try:
            preferred = date_cls.fromisoformat(payload.preferred_date)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail="preferred_date must be YYYY-MM-DD"
            ) from exc

    data = {
        "name": payload.name,
        "email": payload.email,
        "phone": payload.phone,
        "instagram": payload.instagram,
        "telegram": payload.telegram,
        "style": style,
        "placement": payload.placement,
        "approx_size": payload.approx_size,
        "is_color": payload.is_color,
        "description": payload.description,
        "budget_min": payload.budget_min,
        "budget_max": payload.budget_max,
        "preferred_date": preferred,
        "preferred_time": payload.preferred_time,
        "contact_consent": payload.contact_consent,
        "source": "api",
    }

    try:
        booking = create_booking_from_payload(data, files=[])
    except BookingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    notify_new_booking(booking)
    return BookingCreated(
        reference=booking.reference,
        status=booking.status,
        message="Request received. The studio replies by email.",
    )


@router.get(
    "/bookings/{reference}",
    response_model=BookingPublic,
    summary="Look up a booking by reference",
)
def get_booking(reference: str, email: str):
    """
    A booking is retrievable only with BOTH its reference and the client's email.

    References are random, but a reference alone must not reveal anything: requiring the
    matching email makes the endpoint non-enumerable.
    """
    _ensure_django()
    from apps.booking.models import Booking

    booking = (
        Booking.objects.filter(reference__iexact=reference, client__email__iexact=email)
        .select_related("client")
        .first()
    )
    if booking is None:
        # Same response whether the reference is wrong or the email does not match --
        # otherwise the error distinguishes "exists" from "not yours".
        raise HTTPException(status_code=404, detail="No booking found for that reference")

    return BookingPublic(
        reference=booking.reference,
        status=booking.status,
        created_at=booking.created_at,
        preferred_date=booking.preferred_date.isoformat() if booking.preferred_date else None,
    )


# --------------------------------------------------------------------------------------
# Contact
# --------------------------------------------------------------------------------------
@router.post(
    "/contact",
    status_code=status.HTTP_201_CREATED,
    summary="Submit a contact message",
)
def create_contact(payload: ContactCreate, request: Request):
    _ensure_django()
    contact_limiter.check(client_key(request), request)

    from apps.contact.models import ContactMessage

    msg = ContactMessage.objects.create(
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        subject=payload.subject,
        message=payload.message,
    )
    logger.info("contact message %s received from %s", msg.pk, msg.email)
    return {"detail": "Message received. The studio replies by email.", "id": msg.pk}
