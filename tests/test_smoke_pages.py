"""
Smoke tests: every public URL in the map must respond with the expected status
against an EMPTY database.

This is the Phase 1 gate. An empty database is the hardest case: it is exactly the
state a fresh install is in, and the state in which a careless template 500s. These
tests caught the missing template-tag registration during development.
"""

import pytest
from django.urls import reverse

PUBLIC_URLS = [
    ("core:home", 200),
    ("healthz", 200),
    ("artists:about", 200),
    ("tattoos:list", 200),
    ("styles:index", 200),
    ("artworks:list", 200),
    ("gallery:index", 200),
    ("shop:list", 200),
    ("contact:index", 200),
    ("booking:create", 200),
]


@pytest.mark.django_db
@pytest.mark.parametrize(("url_name", "expected"), PUBLIC_URLS)
def test_public_url_responds(client, url_name, expected):
    """Every public page renders on an empty database."""
    response = client.get(reverse(url_name))
    assert response.status_code == expected, f"{url_name} returned {response.status_code}"


@pytest.mark.django_db
def test_healthz_reports_database_status(client):
    response = client.get(reverse("healthz"))
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"] == "ok"


@pytest.mark.django_db
def test_unknown_url_returns_404(client):
    assert client.get("/this-page-does-not-exist/").status_code == 404


@pytest.mark.django_db
def test_design_system_is_gated_when_not_staff(client, settings):
    """
    The design-system reference must never be publicly reachable.

    Two behaviours are asserted: with the page enabled, an anonymous visitor is
    redirected to login; with it disabled (the production case), it 404s.
    """
    settings.DESIGN_SYSTEM_ENABLED = True
    response = client.get(reverse("design_system"))
    assert response.status_code == 302
    assert "login" in response["Location"]

    settings.DESIGN_SYSTEM_ENABLED = False
    assert client.get(reverse("design_system")).status_code == 404
