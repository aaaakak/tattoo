"""
Public site behaviour: SEO, sitemaps, filtering, pagination, booking flow.

These cover the surfaces built in Phases 4-9 that the earlier suites did not reach —
particularly the metadata system and the booking workflow, which are easy to break
invisibly because a missing canonical URL does not raise anything.
"""

from __future__ import annotations

import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.booking.models import Booking
from apps.clients.models import Client


@pytest.fixture
def seeded(db):
    call_command("seed_placeholders", verbosity=0)


@pytest.fixture
def with_work(db):
    """A published tattoo and artwork, so list views have something to render."""
    from apps.artworks.models import Artwork, ArtworkCategory
    from apps.tattoos.models import Tattoo, TattooStyle

    style = TattooStyle.objects.create(name="Gothic", slug="gothic")
    tattoo = Tattoo.objects.create(
        title="Test Piece", slug="test-piece", status=Tattoo.Status.PUBLISHED,
        placement="Forearm", is_featured=True,
    )
    tattoo.styles.add(style)

    cat = ArtworkCategory.objects.create(name="Paintings", slug="paintings")
    Artwork.objects.create(
        title="Test Painting", slug="test-painting", category=cat,
        status=Artwork.Status.PUBLISHED, medium="Oil on canvas", year=2026,
    )
    return {"tattoo": tattoo, "style": style, "artwork": cat}


# --------------------------------------------------------------------------------------
# SEO / metadata
# --------------------------------------------------------------------------------------
@pytest.mark.django_db
def test_home_has_title_description_and_canonical(client, seeded):
    body = client.get(reverse("core:home")).content.decode()
    assert "<title>" in body
    assert 'name="description"' in body
    assert 'rel="canonical"' in body


@pytest.mark.django_db
def test_open_graph_tags_present(client, seeded):
    body = client.get(reverse("core:home")).content.decode()
    assert 'property="og:title"' in body
    assert 'property="og:type"' in body
    assert 'name="twitter:card"' in body


@pytest.mark.django_db
def test_structured_data_is_valid_json(client, seeded):
    """The JSON-LD must parse, or search engines silently ignore it."""
    import json
    import re

    body = client.get(reverse("core:home")).content.decode()
    blocks = re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', body, re.DOTALL
    )
    assert blocks, "no JSON-LD found on the home page"
    for block in blocks:
        parsed = json.loads(block)
        assert "@context" in parsed
        assert "@type" in parsed


@pytest.mark.django_db
def test_structured_data_escapes_hostile_content(client, seeded):
    """
    A title containing </script> must not be able to break out of the script block.

    This is the XSS vector in JSON-LD: the payload is inside a <script> element, so an
    unescaped closing tag becomes executable markup.
    """
    from apps.core.models import SiteSettings

    site = SiteSettings.load()
    site.site_name = "</script><img src=x onerror=alert(1)>"
    site.save()

    body = client.get(reverse("core:home")).content.decode()
    assert "<img src=x onerror" not in body, "JSON-LD allowed markup injection"


@pytest.mark.django_db
def test_detail_page_title_uses_the_object_title(client, with_work):
    body = client.get(reverse("tattoos:detail", args=["test-piece"])).content.decode()
    assert "Test Piece" in body
    assert "<title>" in body


@pytest.mark.django_db
def test_confirmation_page_is_noindex(client, seeded):
    """A booking confirmation must never be indexed."""
    body = client.get(
        reverse("booking:success", args=["TW-ABC123"])
    ).content.decode()
    assert "noindex" in body


@pytest.mark.django_db
def test_booking_form_is_noindex(client, seeded):
    body = client.get(reverse("booking:create")).content.decode()
    assert "noindex" in body


# --------------------------------------------------------------------------------------
# Sitemaps and robots
# --------------------------------------------------------------------------------------
@pytest.mark.django_db
def test_robots_txt_disallows_private_paths(client):
    body = client.get(reverse("robots")).content.decode()
    for path in ("/admin/", "/booking/success/", "/design-system/"):
        assert f"Disallow: {path}" in body
    assert "Sitemap:" in body


@pytest.mark.django_db
def test_sitemap_index_generates(client, with_work):
    response = client.get(reverse("sitemap"))
    assert response.status_code == 200
    assert b"<urlset" in response.content


@pytest.mark.django_db
def test_sitemap_excludes_drafts(client, with_work):
    """A draft must never appear in the sitemap."""
    from apps.tattoos.models import Tattoo

    Tattoo.objects.create(title="Secret Draft", slug="secret-draft", status=Tattoo.Status.DRAFT)
    body = client.get(reverse("sitemap")).content.decode()
    assert "secret-draft" not in body
    assert "test-piece" in body


@pytest.mark.django_db
def test_section_sitemaps_resolve(client, with_work):
    for section in ("pages", "tattoos", "styles", "artworks", "products"):
        response = client.get(f"/sitemap-{section}.xml")
        assert response.status_code == 200, f"sitemap-{section} failed"


# --------------------------------------------------------------------------------------
# Filtering and pagination
# --------------------------------------------------------------------------------------
@pytest.mark.django_db
def test_tattoo_filter_by_style(client, with_work):
    response = client.get(reverse("tattoos:list"), {"style": "gothic"})
    assert response.status_code == 200
    assert b"Test Piece" in response.content


@pytest.mark.django_db
def test_tattoo_filter_by_nonexistent_style_returns_empty(client, with_work):
    response = client.get(reverse("tattoos:list"), {"style": "does-not-exist"})
    assert response.status_code == 200
    assert b"Test Piece" not in response.content


@pytest.mark.django_db
def test_tattoo_search(client, with_work):
    hit = client.get(reverse("tattoos:list"), {"q": "Test"})
    miss = client.get(reverse("tattoos:list"), {"q": "zzzznothing"})
    assert b"Test Piece" in hit.content
    assert b"Test Piece" not in miss.content


@pytest.mark.django_db
def test_artwork_filter_by_category(client, with_work):
    response = client.get(reverse("artworks:list"), {"category": "paintings"})
    assert response.status_code == 200
    assert b"Test Painting" in response.content


@pytest.mark.django_db
def test_filters_survive_without_javascript(client, with_work):
    """
    Filtering must be link-based.

    Filters rendered as buttons would make the portfolio unusable without JS, and would
    make every filtered view unshareable and unindexable.
    """
    body = client.get(reverse("tattoos:list")).content.decode()
    assert 'class="filter-rail"' in body
    assert 'href="?style=gothic"' in body


@pytest.mark.django_db
def test_pagination_is_link_based(client, seeded):
    """Every page of the portfolio must be reachable by a crawler."""
    from apps.tattoos.models import Tattoo

    for i in range(14):
        Tattoo.objects.create(
            title=f"Piece {i:02d}", slug=f"piece-{i:02d}", status=Tattoo.Status.PUBLISHED
        )
    body = client.get(reverse("tattoos:list")).content.decode()
    assert "pagination" in body
    assert "page=2" in body


# --------------------------------------------------------------------------------------
# Booking flow
# --------------------------------------------------------------------------------------
@pytest.mark.django_db
def test_booking_form_renders_all_required_fields(client, seeded):
    body = client.get(reverse("booking:create")).content.decode()
    for field in ("name", "email", "description", "placement", "preferred_date", "contact_consent"):
        assert f'name="{field}"' in body, f"missing field: {field}"


@pytest.mark.django_db
def test_booking_form_has_a_honeypot(client, seeded):
    body = client.get(reverse("booking:create")).content.decode()
    assert 'name="website"' in body
    assert "honeypot" in body


@pytest.mark.django_db
def test_booking_submission_creates_client_and_booking(client, seeded):


    # Use a date the studio actually has availability for, so the booking is accepted.
    from apps.booking.services import next_open_days

    open_days = next_open_days(1)
    payload = {
        "name": "Test Client",
        "email": "client@example.com",
        "description": "A blackwork raven across the forearm with geometric elements.",
        "placement": "Forearm",
        "contact_consent": "on",
    }
    if open_days:
        payload["preferred_date"] = open_days[0].isoformat()

    response = client.post(reverse("booking:create"), payload)
    assert response.status_code == 302, "a valid booking should redirect to the confirmation"

    booking = Booking.objects.get(client__email="client@example.com")
    assert booking.reference.startswith("TW-")
    assert booking.status == Booking.Status.NEW
    assert booking.contact_consent is True
    assert Client.objects.filter(email="client@example.com").exists()


@pytest.mark.django_db
def test_booking_rejects_without_consent(client, seeded):
    response = client.post(reverse("booking:create"), {
        "name": "No Consent",
        "email": "noconsent@example.com",
        "description": "A long enough description of the idea.",
    })
    assert response.status_code == 400
    assert not Booking.objects.filter(client__email="noconsent@example.com").exists()


@pytest.mark.django_db
def test_booking_rejects_a_honeypot_filled_submission(client, seeded):
    response = client.post(reverse("booking:create"), {
        "name": "Bot",
        "email": "bot@example.com",
        "description": "A long enough description of the idea.",
        "contact_consent": "on",
        "website": "http://spam.example.com",
    })
    assert response.status_code == 400
    assert not Booking.objects.filter(client__email="bot@example.com").exists()


@pytest.mark.django_db
def test_booking_reuses_an_existing_client_by_email(client, seeded):
    """A returning client must accumulate history, not be duplicated."""
    Client.objects.create(name="Returning", email="returning@example.com")

    client.post(reverse("booking:create"), {
        "name": "Returning",
        "email": "returning@example.com",
        "description": "A second idea, described in enough detail.",
        "contact_consent": "on",
    })
    assert Client.objects.filter(email="returning@example.com").count() == 1


@pytest.mark.django_db
def test_booking_closed_when_the_switch_is_off(client, seeded):
    from apps.core.models import SiteSettings

    site = SiteSettings.load()
    site.booking_open = False
    site.save()

    response = client.post(reverse("booking:create"), {
        "name": "X", "email": "x@example.com",
        "description": "A long enough description here.",
        "contact_consent": "on",
    })
    assert response.status_code == 403


@pytest.mark.django_db
def test_availability_api_rejects_bad_input(client, seeded):
    assert client.get(reverse("booking:availability_days"), {"month": "99"}).status_code == 400
    assert client.get(reverse("booking:availability_slots"), {"date": "nope"}).status_code == 400


@pytest.mark.django_db
def test_availability_api_returns_slots(client, seeded):
    response = client.get(reverse("booking:availability_slots"), {"date": "2026-10-06"})
    assert response.status_code == 200
    body = response.json()
    assert "slots" in body and "summary" in body


# --------------------------------------------------------------------------------------
# Accessibility basics
# --------------------------------------------------------------------------------------
@pytest.mark.django_db
def test_every_image_has_an_alt_attribute(client, seeded):
    """alt text is an accessibility requirement, not a nicety."""
    import re

    for name in ("core:home", "tattoos:list", "artworks:list"):
        body = client.get(reverse(name)).content.decode()
        for tag in re.findall(r"<img[^>]*>", body):
            assert "alt=" in tag, f"image without alt on {name}: {tag[:90]}"


@pytest.mark.django_db
def test_skip_link_present(client, seeded):
    body = client.get(reverse("core:home")).content.decode()
    assert "skip-link" in body


@pytest.mark.django_db
def test_form_inputs_have_labels(client, seeded):
    import re

    body = client.get(reverse("booking:create")).content.decode()
    labels = set(re.findall(r'<label[^>]*for="([^"]+)"', body))
    inputs = set(re.findall(r'<(?:input|select|textarea)[^>]*id="([^"]+)"', body))
    # every visible input should have a matching label
    unlabelled = {i for i in inputs if i not in labels and not i.startswith("id_website")}
    assert not unlabelled, f"inputs without labels: {sorted(unlabelled)}"
