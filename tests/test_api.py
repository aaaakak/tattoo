"""
API tests.

Includes the SCHEMA CONTRACT TEST, which is the single most important test in the
FastAPI layer: it asserts every column declared in the SQLAlchemy read-mirrors exists in
the live Postgres schema. Without it, a Django field addition silently breaks the API at
runtime; with it, CI fails naming the exact column.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect as sa_inspect

from api_service.db.models import Base
from api_service.db.session import engine
from api_service.main import app


@pytest.fixture(scope="module")
def client():
    # raise_server_exceptions=True so a failing endpoint surfaces the real error rather
    # than a generic 500 that hides the cause during development.
    return TestClient(app, raise_server_exceptions=True)


# --------------------------------------------------------------------------------------
# Schema contract — the guard that makes dual-ORM safe
# --------------------------------------------------------------------------------------
def test_sqlalchemy_mirrors_match_the_live_database():
    """
    Every column in the read-mirrors must exist in Postgres, and every content table the
    mirrors reference must exist.

    A mismatch means a Django migration added or renamed a field that the API does not
    know about. That must fail loudly here rather than as a 500 in production.
    """
    inspector = sa_inspect(engine)
    live_tables = set(inspector.get_table_names())
    problems: list[str] = []

    for mapper in Base.registry.mappers:
        table = mapper.local_table
        if table is None:
            continue
        if table.name not in live_tables:
            problems.append(f"table missing from DB: {table.name}")
            continue

        live_columns = {c["name"] for c in inspector.get_columns(table.name)}
        declared = {c.name for c in table.columns}
        missing = declared - live_columns
        if missing:
            problems.append(f"{table.name}: columns declared but not in DB: {sorted(missing)}")

    assert not problems, "schema contract violated:\n  " + "\n  ".join(problems)


def test_mirror_covers_the_content_tables():
    """
    Guard against the mirrors being emptied, which would make the contract test vacuous.

    Checks Base.metadata rather than registry.mappers: the many-to-many association table
    is declared as a Table (SQLAlchemy resolves `secondary=` by table name), so it is not
    a mapped class and would be missed by a mapper-only check.
    """
    mirrored = set(Base.metadata.tables.keys())
    required = {
        "tattoos_tattoo", "tattoos_tattoostyle", "tattoos_tattoo_styles",
        "artworks_artwork", "artworks_artworkcategory",
        "shop_product", "core_mediaasset", "gallery_galleryimage",
        "core_sitesettings", "artists_artistprofile",
    }
    missing = required - mirrored
    assert not missing, f"mirrors do not cover: {sorted(missing)}"


# --------------------------------------------------------------------------------------
# Meta endpoints
# --------------------------------------------------------------------------------------
def test_healthz(client):
    r = client.get("/api/v1/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_meta(client):
    r = client.get("/api/v1/meta")
    assert r.status_code == 200
    assert r.json()["schema_contract"] == "django-owned"


def test_openapi_schema_generates(client):
    """The typed contract must actually generate, or the docs claim is empty."""
    r = client.get("/api/v1/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    assert "paths" in spec
    assert "/api/v1/tattoos" in spec["paths"]
    assert len(spec["paths"]) >= 12


# --------------------------------------------------------------------------------------
# Content endpoints
# --------------------------------------------------------------------------------------
@pytest.mark.django_db
def test_list_tattoos_returns_paginated_envelope(client):
    r = client.get("/api/v1/tattoos?page_size=2")
    assert r.status_code == 200
    body = r.json()
    for key in ("items", "page", "page_size", "total", "pages"):
        assert key in body, f"pagination envelope missing '{key}'"
    assert len(body["items"]) <= 2


@pytest.mark.django_db
def test_pagination_page_size_is_capped(client):
    """A client must not be able to demand 10,000 rows."""
    r = client.get("/api/v1/tattoos?page_size=9999")
    assert r.status_code == 422


@pytest.mark.django_db
def test_tattoo_detail_404_for_unknown_slug(client):
    r = client.get("/api/v1/tattoos/this-does-not-exist")
    assert r.status_code == 404


@pytest.mark.django_db
def test_tattoo_card_does_not_leak_artist_notes(client):
    """
    The list representation must omit artist notes.

    `artist_notes` is private working commentary; it belongs on the detail page, not in a
    list payload that any client can scrape.
    """
    r = client.get("/api/v1/tattoos?page_size=5")
    assert r.status_code == 200
    for item in r.json()["items"]:
        assert "artist_notes" not in item, "artist_notes leaked into the list payload"


@pytest.mark.django_db
def test_styles_endpoint_lists_styles(client):
    r = client.get("/api/v1/styles")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.django_db
def test_gallery_endpoint(client):
    r = client.get("/api/v1/gallery")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.django_db
def test_site_endpoint_exposes_no_secrets(client):
    """The site payload must contain only public identity fields."""
    r = client.get("/api/v1/site")
    assert r.status_code == 200
    body = r.json()
    for forbidden in ("internal_notes", "secret", "password", "database_url"):
        assert forbidden not in body


# --------------------------------------------------------------------------------------
# Availability
# --------------------------------------------------------------------------------------
@pytest.mark.django_db
def test_availability_days_returns_iso_dates(client):
    r = client.get("/api/v1/availability")
    assert r.status_code == 200
    body = r.json()
    assert "open_days" in body
    for day in body["open_days"]:
        # ISO format is a contract; the frontend parses it directly.
        assert len(day) == 10 and day[4] == "-"


@pytest.mark.django_db
def test_availability_rejects_bad_month(client):
    assert client.get("/api/v1/availability?month=13").status_code == 422


@pytest.mark.django_db
def test_availability_slots_for_a_day(client):
    r = client.get("/api/v1/availability/2026-10-06")
    assert r.status_code == 200
    body = r.json()
    assert "slots" in body
    assert isinstance(body["slots"], list)


@pytest.mark.django_db
def test_availability_slots_rejects_bad_date(client):
    assert client.get("/api/v1/availability/not-a-date").status_code == 422


# --------------------------------------------------------------------------------------
# Booking — validation and enumeration resistance
# --------------------------------------------------------------------------------------
@pytest.mark.django_db
def test_booking_requires_consent(client):
    r = client.post("/api/v1/bookings", json={
        "name": "Test", "email": "t@example.com",
        "description": "A long enough description",
        "contact_consent": False,
    })
    assert r.status_code == 422


@pytest.mark.django_db
def test_booking_requires_a_real_email(client):
    r = client.post("/api/v1/bookings", json={
        "name": "Test", "email": "not-an-email",
        "description": "A long enough description",
        "contact_consent": True,
    })
    assert r.status_code == 422


@pytest.mark.django_db
def test_booking_rejects_a_short_description(client):
    r = client.post("/api/v1/bookings", json={
        "name": "Test", "email": "t@example.com",
        "description": "short",
        "contact_consent": True,
    })
    assert r.status_code == 422


@pytest.mark.django_db
def test_booking_lookup_requires_matching_email(client):
    """
    A booking reference alone must reveal nothing.

    This makes the endpoint non-enumerable: guessing a reference returns 404 unless the
    requester also knows the client's email address.
    """
    r = client.get("/api/v1/bookings/TW-ABC123?email=wrong@example.com")
    assert r.status_code == 404


@pytest.mark.django_db
def test_booking_lookup_404_is_indistinguishable(client):
    """Wrong reference and wrong email must produce the same response."""
    r1 = client.get("/api/v1/bookings/TW-NOPE00?email=a@example.com")
    r2 = client.get("/api/v1/bookings/TW-ABC123?email=wrong@example.com")
    assert r1.status_code == r2.status_code == 404
    assert r1.json() == r2.json()


# --------------------------------------------------------------------------------------
# Search
# --------------------------------------------------------------------------------------
@pytest.mark.django_db
def test_search_requires_a_minimum_query_length(client):
    assert client.get("/api/v1/search?q=a").status_code == 422


@pytest.mark.django_db
def test_search_returns_grouped_results(client):
    r = client.get("/api/v1/search?q=gothic")
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "gothic"
    assert "groups" in body


@pytest.mark.django_db
def test_search_with_no_matches_is_empty_not_an_error(client):
    r = client.get("/api/v1/search?q=zzzzzznotfound")
    assert r.status_code == 200
    assert r.json()["total"] == 0
