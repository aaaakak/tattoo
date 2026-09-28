"""
Availability engine — the correctness core of the booking system.

Framework-free by design: no Django imports, so both the Django views and the FastAPI
layer call the exact same function and the no-double-booking rule exists exactly once
(see docs/architecture.md §5).

The rule is defended twice:
  1. Here — application-level, producing a friendly reason per slot.
  2. In Postgres — the EXCLUDE USING gist constraint on booking_appointment, which makes
     a race-condition double-booking impossible even if two requests pass the check
     simultaneously. This function gives good errors; the constraint gives truth.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date as date_cls
from datetime import datetime, time, timedelta

# Why the minimum lead time exists: the artist needs room to prepare a design. Booking a
# bespoke tattoo for tomorrow morning is not a workable request, so same-day and
# next-morning slots are withheld rather than accepted and cancelled later.
DEFAULT_LEAD_HOURS = 24


@dataclass(frozen=True)
class AvalRow:
    """A working window. Mirrors apps.booking.models.Availability without importing it."""

    weekday: int
    start_time: time
    end_time: time
    slot_minutes: int = 60
    is_active: bool = True


@dataclass(frozen=True)
class BlockedRow:
    """A blocked date or range. Mirrors apps.booking.models.BlockedDate."""

    date: date_cls
    end_date: date_cls | None = None
    all_day: bool = True
    start_time: time | None = None
    end_time: time | None = None


@dataclass(frozen=True)
class ApptRow:
    """An existing appointment. Mirrors apps.booking.models.Appointment."""

    start_at: datetime
    end_at: datetime
    status: str = "scheduled"


@dataclass(frozen=True)
class Slot:
    start: datetime
    end: datetime
    available: bool
    reason: str | None = None  # "booked" | "blocked" | "too_soon" | None


# Statuses that occupy the calendar. Cancelled and no-show do NOT block.
BLOCKING_STATUSES = frozenset({"scheduled", "confirmed"})


def _combine(day: date_cls, t: time, tz=None) -> datetime:
    """
    Combine a date and time into a datetime, honouring the timezone.

    CRITICAL: the caller's `now` is timezone-aware (Django's timezone.localtime()), and
    appointment rows are stored timezone-aware. A naive datetime from a bare
    datetime.combine() cannot be compared with either -- Python raises
    "can't compare offset-naive and offset-aware datetimes".

    The engine stays framework-free by accepting an explicit `tz` rather than importing
    Django's timezone helpers; the Django and FastAPI callers both pass their own.
    """
    naive = datetime.combine(day, t)
    if tz is None:
        return naive
    if hasattr(tz, "localize"):  # pytz-style
        return tz.localize(naive)
    return naive.replace(tzinfo=tz)


def _overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    """Half-open interval overlap: [a_start, a_end) vs [b_start, b_end)."""
    return a_start < b_end and b_start < a_end


def compute_slots(
    *,
    day: date_cls,
    availability: Sequence[AvalRow],
    blocked: Sequence[BlockedRow],
    booked: Sequence[ApptRow],
    now: datetime,
    lead_hours: int = DEFAULT_LEAD_HOURS,
    tz=None,
) -> list[Slot]:
    """
    Return every slot for one day, each marked available or not, with a reason.

    Order of resolution:
      1. No active availability row for this weekday -> the day is closed, return [].
      2. Slice the working window(s) into fixed-length slots.
      3. Mark booked  — any blocking appointment overlapping the slot.
      4. Mark blocked — any BlockedDate covering the slot (full-day or partial).
      5. Mark too_soon — inside the minimum lead time.
    """
    windows = [a for a in availability if a.is_active and a.weekday == day.weekday()]
    if not windows:
        return []

    lead_cutoff = now + timedelta(hours=lead_hours)
    slots: list[Slot] = []

    for window in sorted(windows, key=lambda w: w.start_time):
        step = timedelta(minutes=max(15, window.slot_minutes))
        cursor = _combine(day, window.start_time, tz)
        window_end = _combine(day, window.end_time, tz)

        while cursor + step <= window_end:
            slot_start = cursor
            slot_end = cursor + step
            reason: str | None = None

            # 1. Existing appointment?
            for appt in booked:
                if appt.status not in BLOCKING_STATUSES:
                    continue
                if _overlaps(slot_start, slot_end, appt.start_at, appt.end_at):
                    reason = "booked"
                    break

            # 2. Blocked date?
            if reason is None:
                for block in blocked:
                    block_end_date = block.end_date or block.date
                    if not (block.date <= day <= block_end_date):
                        continue
                    if block.all_day or not (block.start_time and block.end_time):
                        reason = "blocked"
                        break
                    if _overlaps(
                        slot_start,
                        slot_end,
                        _combine(day, block.start_time, tz),
                        _combine(day, block.end_time, tz),
                    ):
                        reason = "blocked"
                        break

            # 3. Too soon?
            if reason is None and slot_start < lead_cutoff:
                reason = "too_soon"

            slots.append(
                Slot(start=slot_start, end=slot_end, available=reason is None, reason=reason)
            )
            cursor = slot_end

    return slots


def available_days(
    *,
    start: date_cls,
    end: date_cls,
    availability: Iterable[AvalRow],
    blocked: Iterable[BlockedRow],
    booked: Iterable[ApptRow],
    now: datetime,
    lead_hours: int = DEFAULT_LEAD_HOURS,
    tz=None,
) -> list[date_cls]:
    """
    Which dates in [start, end] have at least one bookable slot.

    Drives the calendar widget. Iterating day by day is fine at this scale (a month is 31
    calls) and keeps the logic identical to compute_slots, which is the point: the
    calendar can never disagree with the slot list.
    """
    availability = list(availability)
    blocked = list(blocked)
    booked = list(booked)

    days: list[date_cls] = []
    cursor = start
    while cursor <= end:
        slots = compute_slots(
            day=cursor,
            availability=availability,
            blocked=blocked,
            booked=booked,
            now=now,
            lead_hours=lead_hours,
            tz=tz,
        )
        if any(s.available for s in slots):
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def summarise(slots: Sequence[Slot]) -> dict[str, int]:
    """Counts per state, for the UI legend and for tests."""
    out = {"available": 0, "booked": 0, "blocked": 0, "too_soon": 0}
    for slot in slots:
        if slot.available:
            out["available"] += 1
        elif slot.reason in out:
            out[slot.reason] += 1
    return out


def is_slot_bookable(
    *, start_at: datetime, end_at: datetime, day_slots: Sequence[Slot]
) -> tuple[bool, str | None]:
    """
    Validate a requested time against a computed day.

    Returns (ok, reason). Used by the booking form and the API so both paths apply the
    identical rule rather than each re-implementing the check.
    """
    for slot in day_slots:
        if slot.start == start_at and slot.end == end_at:
            return (slot.available, slot.reason)

    # Not an exact slot boundary: accept a request that falls inside an available slot's
    # window only if the whole requested range is covered by free time.
    for slot in day_slots:
        if _overlaps(start_at, end_at, slot.start, slot.end):
            if not slot.available:
                return (False, slot.reason)
            if start_at < slot.start or end_at > slot.end:
                return (False, "partial")
    return (False, "outside_hours")
