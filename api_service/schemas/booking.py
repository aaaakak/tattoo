"""
Booking and availability schemas.

`BookingPublic` and `BookingArtist` are separate types on purpose: `internal_notes` and
the client's contact details exist ONLY on the artist type. Separating them by type makes
leaking a private field a compile-time impossibility rather than a review question.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class BookingCreate(BaseModel):
    """Inbound booking request payload."""

    name: str = Field(min_length=1, max_length=160)
    email: EmailStr
    phone: str = Field(default="", max_length=40)
    instagram: str = Field(default="", max_length=80)
    telegram: str = Field(default="", max_length=80)

    style_slug: str | None = None
    placement: str = Field(default="", max_length=80)
    approx_size: str = Field(default="", max_length=40)
    is_color: str = Field(default="undecided", pattern="^(color|black_grey|undecided)$")
    description: str = Field(min_length=10, max_length=5000)

    budget_min: float | None = Field(default=None, ge=0)
    budget_max: float | None = Field(default=None, ge=0)
    preferred_date: str | None = None
    preferred_time: str = Field(default="", max_length=20)

    contact_consent: bool

    @field_validator("contact_consent")
    @classmethod
    def consent_required(cls, v: bool) -> bool:
        if not v:
            raise ValueError("consent is required before a request can be submitted")
        return v

    @field_validator("budget_max")
    @classmethod
    def budget_order(cls, v, info):
        low = info.data.get("budget_min")
        if v is not None and low is not None and v < low:
            raise ValueError("budget_max must be greater than or equal to budget_min")
        return v


class BookingPublic(BaseModel):
    """What the client may see. No internal notes, no third-party contact details."""

    reference: str
    status: str
    created_at: datetime
    preferred_date: str | None = None


class BookingArtist(BookingPublic):
    """Artist-only representation."""

    client_name: str
    client_email: str
    client_phone: str = ""
    style: str | None = None
    placement: str = ""
    approx_size: str = ""
    is_color: str = ""
    description: str = ""
    budget_min: str | None = None
    budget_max: str | None = None
    internal_notes: str = ""
    reference_count: int = 0


class BookingCreated(BaseModel):
    reference: str
    status: str
    message: str


class SlotOut(BaseModel):
    start: datetime
    end: datetime
    available: bool
    reason: str | None = None


class AvailabilityDayOut(BaseModel):
    date: str
    slots: list[SlotOut]
    available_count: int


class AvailabilityDaysOut(BaseModel):
    year: int
    month: int
    open_days: list[str]
    count: int


class ContactCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    email: EmailStr
    phone: str = Field(default="", max_length=40)
    subject: str = Field(default="", max_length=160)
    message: str = Field(min_length=5, max_length=5000)
