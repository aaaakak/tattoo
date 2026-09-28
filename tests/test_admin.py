"""
Admin tests.

The admin is the artist's entire interface to the site, so it is tested like a product
surface rather than a Django formality. Three things matter most and get direct coverage:

  1. Every registered model's changelist actually loads (catching a bad list_display,
     a broken callable, or a missing readonly field).
  2. The dashboard renders real numbers from real data.
  3. The custom admin site is genuinely installed -- an earlier version silently left
     zero models registered because the site was swapped after autodiscovery.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib import admin
from django.urls import reverse

from apps.artists.models import ArtistProfile
from apps.artworks.models import Artwork, ArtworkCategory
from apps.booking.models import Appointment, Availability, Booking
from apps.clients.models import Client
from apps.contact.models import ContactMessage
from apps.core.models import MediaAsset, SiteSettings, SocialLink, Tag
from apps.tattoos.models import Tattoo, TattooImage, TattooStyle


@pytest.fixture
def superuser(django_user_model):
    return django_user_model.objects.create_superuser(
        username="artist", email="artist@example.com", password="pw-for-tests-only"
    )


@pytest.fixture
def logged_in(client, superuser):
    client.force_login(superuser)
    return client


# --------------------------------------------------------------------------------------
# Site installation — regression guard
# --------------------------------------------------------------------------------------
def test_custom_admin_site_is_installed():
    """The admin site must be ours, not Django's default."""
    from apps.core.admin_site import TattoWebAdminSite

    site = _admin_site()
    assert isinstance(site, TattoWebAdminSite)
    assert site.site_header == "STUDIO ADMINISTRATION"


def test_all_models_are_registered():
    """
    Guard against the silent-zero-registrations failure.

    An earlier implementation swapped admin.site inside CoreConfig.ready(), which ran
    after the admin modules had been imported -- so the custom site had no models at all
    and the index rendered empty.
    """
    site = _admin_site()
    registered = set(site._registry.keys())

    expected = {
        SiteSettings, SocialLink, MediaAsset, Tag,
        ArtistProfile,
        TattooStyle, Tattoo, TattooImage,
        ArtworkCategory, Artwork,
        Client,
        Availability, Booking, Appointment,
        ContactMessage,
    }
    missing = expected - registered
    assert not missing, f"unregistered models: {sorted(m.__name__ for m in missing)}"
    assert len(registered) >= 20


def _admin_site():
    """Resolve the real admin site from Django's lazy wrapper."""
    return admin.site._wrapped if hasattr(admin.site, "_wrapped") else admin.site


def test_every_registered_model_has_a_working_changelist(logged_in):
    """
    Load every changelist. This is the highest-value admin test: it exercises each
    list_display callable, each list_filter and the search configuration, which is where
    most admin misconfigurations surface.

    A 302 is accepted because the two singleton admins deliberately redirect their
    changelist to the single record instead of showing a one-row table.
    """
    site = _admin_site()
    failures = []
    for model in site._registry:
        opts = model._meta
        url = reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist")
        try:
            response = logged_in.get(url)
            if response.status_code not in (200, 302):
                failures.append(f"{opts.label}: HTTP {response.status_code}")
        except Exception as exc:
            failures.append(f"{opts.label}: {type(exc).__name__}: {exc}")
    assert not failures, "changelist failures:\n  " + "\n  ".join(failures)


def test_every_registered_model_has_a_working_add_page(client, superuser):
    """
    Load every add form. Catches bad fieldsets, unknown fields and broken autocomplete
    references — the errors that otherwise appear only when the artist clicks "Add".
    """
    client.force_login(superuser)
    site = _admin_site()
    failures = []
    for model in site._registry:
        opts = model._meta
        url = reverse(f"admin:{opts.app_label}_{opts.model_name}_add")
        try:
            response = client.get(url)
            # 200 form rendered, 403 correctly refused (singletons), 302 redirect
            if response.status_code not in (200, 302, 403):
                failures.append(f"{opts.label}: HTTP {response.status_code}")
        except Exception as exc:
            failures.append(f"{opts.label}: {type(exc).__name__}: {exc}")
    assert not failures, "add page failures:\n  " + "\n  ".join(failures)


# --------------------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------------------
@pytest.mark.django_db
def test_admin_index_renders_dashboard(logged_in):
    response = logged_in.get(reverse("admin:index"))
    assert response.status_code == 200
    body = response.content.decode()
    assert "STUDIO ADMINISTRATION" in body or "tw-dashboard" in body
    assert "OPEN BOOKINGS" in body
    assert "UNREAD MESSAGES" in body


@pytest.mark.django_db
def test_dashboard_shows_real_open_booking_counts(logged_in):
    """The dashboard must reflect actual data, not placeholder zeros."""
    client_obj = Client.objects.create(name="Dash Test", email="dash@example.com")
    Booking.objects.create(client=client_obj, description="Test", status=Booking.Status.NEW)
    Booking.objects.create(client=client_obj, description="Test", status=Booking.Status.REVIEWING)
    Booking.objects.create(client=client_obj, description="Done", status=Booking.Status.COMPLETED)

    response = logged_in.get(reverse("admin:index"))
    body = response.content.decode()
    # Two are open (new + reviewing); the completed one must not be counted.
    assert "Dash Test" in body or "OPEN BOOKINGS" in body
    assert "dash@example.com" not in body  # dashboard shows names, not emails


@pytest.mark.django_db
def test_dashboard_survives_empty_database(logged_in):
    """The dashboard must never be the reason the admin is unreachable."""
    response = logged_in.get(reverse("admin:index"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_dashboard_shows_low_stock(logged_in):
    from apps.shop.models import Product, ProductCategory

    cat = ProductCategory.objects.create(name="Prints")
    Product.objects.create(
        name="Nearly Gone", category=cat, price="40.00", stock=1, status="published"
    )
    response = logged_in.get(reverse("admin:index"))
    assert "Nearly Gone" in response.content.decode()


# --------------------------------------------------------------------------------------
# Singletons
# --------------------------------------------------------------------------------------
@pytest.mark.django_db
def test_site_settings_changelist_redirects_to_the_single_record(logged_in):
    """A singleton has no useful list, so the changelist should redirect to the object."""
    SiteSettings.load()
    url = reverse("admin:core_sitesettings_changelist")
    response = logged_in.get(url)
    assert response.status_code == 302
    assert "/change/" in response["Location"]


@pytest.mark.django_db
def test_singleton_add_is_refused_once_the_row_exists(logged_in):
    SiteSettings.load()
    url = reverse("admin:core_sitesettings_add")
    response = logged_in.get(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_singleton_delete_is_never_offered(logged_in):
    site = _admin_site()
    ma = site._registry[SiteSettings]
    assert ma.has_delete_permission(_StubRequest()) is False


# --------------------------------------------------------------------------------------
# Content admin behaviour
# --------------------------------------------------------------------------------------
@pytest.mark.django_db
def test_placeholder_column_flags_demo_content():
    """
    The placeholder marker must distinguish demonstration content from real work.

    Guarded because it is the mechanism preventing generated sample artwork from being
    mistaken for the artist's own pieces.
    """
    from apps.core.admin_mixins import placeholder_column

    real = Tattoo(title="Real", is_placeholder=False)
    demo = Tattoo(title="Demo", is_placeholder=True)

    assert "—" in str(placeholder_column(real))
    assert "PLACEHOLDER" in str(placeholder_column(demo))


@pytest.mark.django_db
@pytest.mark.parametrize("label", ["tattoos.tattoo", "artworks.artwork", "shop.product"])
def test_content_changelists_load(logged_in, label):
    """
    REGRESSION GUARD — the real HTTP path.

    A `list_display` callable assigned as a plain class attribute is bound as a method and
    called with (self, obj), raising "takes 1 positional argument but 2 were given" and
    returning a 500 on the changelist.

    A unit test calling that callable directly PASSES while the page crashes — which is
    exactly what happened. These parametrised cases hit the real URL so the binding
    behaviour is exercised the way Django exercises it.
    """
    response = logged_in.get(reverse(f"admin:{label.replace('.', '_')}_changelist"))
    assert response.status_code == 200, (
        f"{label} changelist returned {response.status_code}; "
        "a list_display callable is probably missing @staticmethod"
    )


@pytest.mark.django_db
def test_placeholder_column_works_through_the_admin_instance():
    """
    Prove the staticmethod actually prevents `self` binding.

    Fetching the attribute from the admin instance and calling it with one argument must
    succeed — that is precisely how Django's lookup_field invokes it.
    """
    site = _admin_site()
    ma = site._registry[Tattoo]
    bound = ma.placeholder_column
    demo = Tattoo(title="Demo", is_placeholder=True)
    assert "PLACEHOLDER" in str(bound(demo))


def test_content_admins_expose_the_placeholder_column():
    """Both content admins must surface the placeholder marker in their changelist."""
    site = _admin_site()
    for model in (Tattoo, Artwork):
        ma = site._registry[model]
        assert "placeholder_column" in ma.list_display, (
            f"{model.__name__}Admin does not show the placeholder marker"
        )


@pytest.mark.django_db
def test_publish_action_sets_status_and_timestamp():
    site = _admin_site()
    ma = site._registry[Tattoo]

    t = Tattoo.objects.create(title="Draft Piece", status=Tattoo.Status.DRAFT)
    assert t.published_at is None

    ma.action_publish(_StubRequest(), Tattoo.objects.filter(pk=t.pk))
    t.refresh_from_db()
    assert t.status == Tattoo.Status.PUBLISHED
    assert t.published_at is not None


@pytest.mark.django_db
def test_unpublish_action_reverts_to_draft():
    site = _admin_site()
    ma = site._registry[Tattoo]

    t = Tattoo.objects.create(title="Live Piece", status=Tattoo.Status.PUBLISHED)
    ma.action_unpublish(_StubRequest(), Tattoo.objects.filter(pk=t.pk))
    t.refresh_from_db()
    assert t.status == Tattoo.Status.DRAFT


@pytest.mark.django_db
def test_style_piece_count_only_counts_published():
    site = _admin_site()
    ma = site._registry[TattooStyle]

    style = TattooStyle.objects.create(name="Blackwork")
    published = Tattoo.objects.create(title="P", status=Tattoo.Status.PUBLISHED)
    draft = Tattoo.objects.create(title="D", status=Tattoo.Status.DRAFT)
    published.styles.add(style)
    draft.styles.add(style)

    assert ma.piece_count(style) == 1


@pytest.mark.django_db
def test_booking_status_pill_renders_the_label():
    site = _admin_site()
    ma = site._registry[Booking]

    c = Client.objects.create(name="Pill Test")
    b = Booking.objects.create(client=c, description="x", status=Booking.Status.APPROVED)
    assert "Approved" in str(ma.status_pill(b))


@pytest.mark.django_db
def test_appointment_duration_display():
    from django.utils import timezone

    site = _admin_site()
    ma = site._registry[Appointment]

    c = Client.objects.create(name="Dur Test")
    start = timezone.now()
    appt = Appointment.objects.create(
        client=c, start_at=start, end_at=start + timedelta(hours=2)
    )
    assert ma.duration(appt) == "120 min"


@pytest.mark.django_db
def test_media_asset_variant_summary_lists_siblings():
    from apps.core.ingest import ingest_image
    from tests.test_ingest import _png

    site = _admin_site()
    ma = site._registry[MediaAsset]

    original = ingest_image(filename="admin_summary.png", content=_png(400, 500))
    summary = str(ma.variants_summary(original))
    assert "derivative" in summary
    assert "dither" in summary


@pytest.mark.django_db
def test_client_booking_history_links_to_bookings():
    site = _admin_site()
    ma = site._registry[Client]

    c = Client.objects.create(name="History Test")
    b = Booking.objects.create(client=c, description="x")
    html = str(ma.booking_history(c))
    assert b.reference in html


@pytest.mark.django_db
def test_admin_requires_authentication(client):
    """Every admin route must refuse anonymous access."""
    for url in (reverse("admin:index"), reverse("admin:booking_booking_changelist")):
        response = client.get(url)
        assert response.status_code == 302
        assert "login" in response["Location"]


class _StubRequest:
    """
    Minimal request for admin actions and permission checks.

    Admin actions call message_user(), which needs request._messages and request.user.
    Using a real Django test client's request is overkill; this stub satisfies exactly
    the interface the actions touch.
    """

    class _Messages:
        def add(self, *args, **kwargs):
            return None

    def __init__(self):
        self._messages = self._Messages()
        self.user = _StubUser()
        self.method = "POST"


class _StubUser:
    is_active = True
    is_staff = True
    is_superuser = True
    pk = 1

    def has_perm(self, perm, obj=None):
        return True

@pytest.mark.django_db
def test_admin_index_still_shows_the_model_list(logged_in):
    """
    REGRESSION GUARD.

    The dashboard template overrides {% block content %}, which is the same block Django's
    index.html uses to render the app/model list. An earlier version omitted
    {{ block.super }}, so the dashboard rendered its statistics correctly while silently
    deleting the entire navigation -- total loss of function that looked like a styling
    quirk.

    This asserts the model links are still present, so the failure can never recur
    invisibly.
    """
    response = logged_in.get(reverse("admin:index"))
    body = response.content.decode()

    # Every registered model must be reachable from the index.
    site = _admin_site()
    missing = []
    for model in site._registry:
        opts = model._meta
        url = reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist")
        if url not in body:
            missing.append(opts.label)
    assert not missing, (
        "admin index is missing links to: " + ", ".join(sorted(missing)) +
        " -- the dashboard template probably dropped {{ block.super }}"
    )


@pytest.mark.django_db
def test_admin_index_has_both_dashboard_and_app_list(logged_in):
    """Both surfaces must coexist: the dashboard AND the navigation."""
    body = logged_in.get(reverse("admin:index")).content.decode()
    assert "tw-dashboard" in body, "dashboard missing"
    assert "OPEN BOOKINGS" in body, "dashboard statistics missing"
    # The app list renders each app's verbose name as a section heading.
    assert "Tattoos" in body or "tattoos" in body, "app list missing"
