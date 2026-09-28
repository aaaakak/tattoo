"""
Site-wide context processor.

Supplies the navigation, SiteSettings and ArtistProfile to *every* template.

Hard rule: this must NEVER raise, even on a completely empty database. Every page of the
site runs through here, so a single unguarded ``SiteSettings.objects.get()`` would 500 the
entire site before the artist has logged in and created anything. Every lookup is therefore
defensive and returns a safe default.
"""

from __future__ import annotations

from typing import Any

# Ordered navigation. `label` is the mono nav text; `url_name` is a namespaced route.
NAV_ITEMS: list[dict[str, str]] = [
    {"label": "TATTOOS", "url_name": "tattoos:list"},
    {"label": "ARTWORK", "url_name": "artworks:list"},
    {"label": "GALLERY", "url_name": "gallery:index"},
    {"label": "ABOUT", "url_name": "artists:about"},
    {"label": "SHOP", "url_name": "shop:list"},
]


def site_context(request) -> dict[str, Any]:
    """Return site-wide template context. Never raises."""
    settings_obj = None
    artist = None
    social_links: list[Any] = []

    try:
        from apps.core.models import SiteSettings

        settings_obj = SiteSettings.load()
    except Exception:
        settings_obj = None

    try:
        from apps.artists.models import ArtistProfile

        artist = ArtistProfile.load()
    except Exception:
        artist = None

    try:
        from apps.core.models import SocialLink

        social_links = list(SocialLink.objects.filter(is_active=True).order_by("order", "label"))
    except Exception:
        social_links = []

    # Booking CTA is shown only when both switches allow it.
    booking_open = bool(
        (settings_obj.booking_open if settings_obj else True)
        and (artist.is_booking_open if artist else True)
    )

    from django.conf import settings as dj_settings

    return {
        "static_version": getattr(dj_settings, "STATIC_VERSION", "dev"),
        "nav_items": NAV_ITEMS,
        "site": settings_obj,
        "site_settings": settings_obj,
        "artist": artist,
        "social_links": social_links,
        "booking_open": booking_open,
    }
