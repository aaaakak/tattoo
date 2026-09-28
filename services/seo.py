"""
SEO and metadata helpers.

Framework-light and importable anywhere. Provides the fallback chain documented in
docs/erd.md section 12 and the structured-data builders used by Phase 12.

Design rule: every ``get_*`` function returns a usable value or an empty string. Nothing
here raises, because a missing meta description must never break a page render.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings


def absolute(request, path: str) -> str:
    """Build an absolute URL for canonical and social metadata."""
    if not path:
        return ""
    if path.startswith(("http://", "https://")):
        return path
    return request.build_absolute_uri(path)


def canonical_url(request) -> str:
    """
    Canonical URL for the current page.

    Query strings are stripped: filtered views of a portfolio are the same canonical
    resource as the unfiltered one, and letting ?page=2 be canonical splits ranking.
    """
    return absolute(request, request.path)


def image_absolute(request, asset) -> str:
    if not asset or not getattr(asset, "file", None):
        return ""
    try:
        return absolute(request, asset.file.url)
    except ValueError:
        # File field set but no file on disk.
        return ""


def resolve_meta_title(obj, fallback: str) -> str:
    """Object override -> site default -> fallback."""
    if obj is not None and hasattr(obj, "get_meta_title"):
        value = obj.get_meta_title()
        if value:
            return value
    if hasattr(obj, "meta_title") and getattr(obj, "meta_title", ""):
        return obj.meta_title
    return fallback


def resolve_meta_description(obj, site, fallback: str = "") -> str:
    """Object override -> object description -> site default -> fallback."""
    if obj is not None:
        if hasattr(obj, "get_meta_description"):
            value = obj.get_meta_description()
            if value:
                return value
        if getattr(obj, "meta_description", ""):
            return obj.meta_description
        description = getattr(obj, "description", "")
        if description:
            return _truncate(description, 320)
    if site is not None and site.default_meta_description:
        return site.default_meta_description
    return fallback


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0] + "…"


def og_image_for(obj, site):
    """Best available social image: the object's primary image, else the site default."""
    if obj is not None:
        if getattr(obj, "og_image", None):
            return obj.og_image
        getter = getattr(obj, "primary_image", None)
        if callable(getter):
            img = getter()
            if img is not None:
                return getattr(img, "asset", img)
    if site is not None:
        return site.og_default_image
    return None


# --------------------------------------------------------------------------------------
# Structured data (JSON-LD)
# --------------------------------------------------------------------------------------
def person_schema(request, artist, site) -> dict[str, Any]:
    """schema.org/Person for the artist."""
    data: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": artist.display_name if artist else (site.site_name if site else ""),
    }
    if artist:
        if artist.statement:
            data["description"] = artist.statement
        if artist.location:
            data["address"] = {"@type": "PostalAddress", "addressLocality": artist.location}
        if artist.email:
            data["email"] = artist.email
        if artist.portrait:
            data["image"] = image_absolute(request, artist.portrait)
        if artist.years_experience:
            data["knowsAbout"] = ["Tattoo", "Tattoo design", "Illustration"]
    return data


def creative_work_schema(request, obj, *, kind: str = "CreativeWork") -> dict[str, Any]:
    """schema.org/CreativeWork (or VisualArtwork) for a tattoo or artwork."""
    data: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": kind,
        "name": getattr(obj, "title", ""),
        "url": absolute(request, obj.get_absolute_url()) if hasattr(obj, "get_absolute_url") else "",
    }
    if getattr(obj, "description", ""):
        data["description"] = obj.description
    img = og_image_for(obj, None)
    if img is not None and getattr(img, "file", None):
        data["image"] = image_absolute(request, img)
    creator = getattr(obj, "artist", None)
    if creator:
        data["creator"] = {"@type": "Person", "name": creator.display_name}
    if getattr(obj, "session_date", None):
        data["dateCreated"] = obj.session_date.isoformat()
    if getattr(obj, "year", None):
        data["dateCreated"] = str(obj.year)
    return data


def product_schema(request, product) -> dict[str, Any]:
    """schema.org/Product for a shop item, honest about availability."""
    availability_map = {
        "in_stock": "https://schema.org/InStock",
        "made_to_order": "https://schema.org/PreOrder",
        "sold_out": "https://schema.org/SoldOut",
        "coming_soon": "https://schema.org/PreOrder",
    }
    data: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product.name,
        "url": absolute(request, product.get_absolute_url()),
        "offers": {
            "@type": "Offer",
            "price": str(product.price),
            "priceCurrency": product.currency,
            "availability": availability_map.get(product.availability, "https://schema.org/InStock"),
        },
    }
    if product.description:
        data["description"] = product.description
    img = og_image_for(product, None)
    if img is not None and getattr(img, "file", None):
        data["image"] = image_absolute(request, img)
    return data


def breadcrumb_schema(request, crumbs: list[tuple[str, str]]) -> dict[str, Any]:
    """
    schema.org/BreadcrumbList.

    The site is shallow (portfolio pages are two levels deep) so breadcrumbs are not
    shown in the UI, but search engines benefit from the explicit hierarchy.
    """
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "name": name,
                "item": absolute(request, url),
            }
            for i, (name, url) in enumerate(crumbs)
        ],
    }


def site_base_url(request) -> str:
    """Origin for sitemaps and canonical fallbacks."""
    return f"{request.scheme}://{request.get_host()}" if hasattr(request, "get_host") else ""


def default_og_type(obj) -> str:
    """Open Graph type for the object."""
    from apps.artworks.models import Artwork
    from apps.shop.models import Product
    from apps.tattoos.models import Tattoo

    if isinstance(obj, Product):
        return "product"
    if isinstance(obj, (Tattoo, Artwork)):
        return "article"
    return "website"


def social_image_dimensions(site) -> tuple[int, int]:
    """Open Graph image dimensions, required for some crawlers to render large cards."""
    if site is not None and site.og_default_image:
        img = site.og_default_image
        return (img.width or 1200, img.height or 630)
    return (1200, 630)


def build_context(request, *, obj=None, title: str = "", description: str = "",
                  og_type: str = "", canonical: str = "", robots: str = "",
                  structured_data: list[dict] | None = None) -> dict[str, Any]:
    """
    Assemble the metadata block for head.html.

    Single entry point so a view cannot accidentally set a title without a description,
    or forget the canonical URL.
    """
    site = None
    artist = None
    try:
        from apps.core.models import SiteSettings

        site = SiteSettings.load()
    except Exception:
        pass
    try:
        from apps.artists.models import ArtistProfile

        artist = ArtistProfile.load()
    except Exception:
        pass

    fallback_title = site.site_name if site else settings.SITE_NAME
    if artist and artist.display_name:
        fallback_title = f"{artist.display_name} — {fallback_title}"

    meta_title = resolve_meta_title(obj, title or fallback_title)
    meta_description = resolve_meta_description(obj, site, description)
    og_image = og_image_for(obj, site)
    width, height = social_image_dimensions(site)

    return {
        "meta_title": meta_title,
        "meta_description": meta_description,
        "meta_canonical": canonical or canonical_url(request),
        "meta_og_type": og_type or default_og_type(obj),
        "meta_og_image": image_absolute(request, og_image),
        "meta_og_image_width": width,
        "meta_og_image_height": height,
        "meta_robots": robots,
        "meta_structured_data": structured_data or [],
        "meta_site_name": site.site_name if site else settings.SITE_NAME,
    }
