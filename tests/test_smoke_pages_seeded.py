"""
Smoke tests against a SEEDED database.

Complements the empty-database tests: proves the templates actually render the CMS
content rather than only surviving its absence.
"""

import pytest
from django.core.management import call_command
from django.urls import reverse


@pytest.fixture
def seeded(db):
    call_command("seed_placeholders")


@pytest.mark.django_db
def test_home_renders_cms_hero_and_statement(client, seeded):
    response = client.get(reverse("core:home"))
    assert response.status_code == 200
    body = response.content.decode()

    # Hero headline from SiteSettings
    assert "MOVES" in body
    assert "WITH YOU" in body
    # Artist statement
    assert "INK IS ONLY THE MEDIUM" in body
    # Statistics from the CMS
    assert "1200+" in body
    assert "SIGNATURE STYLES" in body


@pytest.mark.django_db
def test_styles_page_lists_seeded_styles(client, seeded):
    response = client.get(reverse("styles:index"))
    assert response.status_code == 200
    body = response.content.decode()
    for name in ("Blackwork", "Fine Line", "Ornamental"):
        assert name in body


@pytest.mark.django_db
def test_about_page_renders_biography(client, seeded):
    response = client.get(reverse("artists:about"))
    assert response.status_code == 200
    assert "INK IS ONLY THE MEDIUM" in response.content.decode()


@pytest.mark.django_db
def test_seed_command_is_idempotent(seeded):
    """Running the seeder twice must not duplicate rows."""
    from apps.tattoos.models import TattooStyle

    before = TattooStyle.objects.count()
    call_command("seed_placeholders")
    assert TattooStyle.objects.count() == before
