"""
Root URL configuration.

Two API trees, one owner each (see docs/url-map.md):
  /api/v1/*        -> FastAPI   (public, cacheable JSON)  -- different process
  /api/django/v1/* -> DRF       (authenticated, administrative)

The prefix tells you which stack and which auth model applies. This separation is
deliberate: it makes an accidental route collision impossible rather than unlikely.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from apps.core import views as core_views
from apps.core.sitemaps import (
    ArtworkCategorySitemap,
    ArtworkSitemap,
    GalleryCollectionSitemap,
    ProductSitemap,
    StaticViewSitemap,
    TattooSitemap,
    TattooStyleSitemap,
)

# Named section sitemaps. One index, several sections -- so a crawl budget spent on the
# portfolio is not diluted by shop pages it does not care about.
SITEMAPS = {
    "pages": StaticViewSitemap,
    "tattoos": TattooSitemap,
    "styles": TattooStyleSitemap,
    "artworks": ArtworkSitemap,
    "categories": ArtworkCategorySitemap,
    "collections": GalleryCollectionSitemap,
    "products": ProductSitemap,
}

urlpatterns = [
    # --- Admin / CMS -------------------------------------------------------------
    path("admin/", admin.site.urls),

    # --- Infra -------------------------------------------------------------------
    path("healthz/", core_views.healthz, name="healthz"),
    path("robots.txt", core_views.robots, name="robots"),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap"),
    # Individual section sitemaps. Django's sitemap view needs an explicit section name;
    # without these routes only the index is reachable.
    path(
        "sitemap-<section>.xml",
        sitemap,
        {"sitemaps": SITEMAPS},
        name="sitemap-section",
    ),
    # Design-system reference page: staff-only, DEBUG-gated. This is how the visual
    # system is verified rather than eyeballed.
    path("design-system/", core_views.design_system, name="design_system"),

    # --- Public site -------------------------------------------------------------
    path("", include("apps.core.urls")),
    path("tattoos/", include("apps.tattoos.urls")),
    path("styles/", include("apps.tattoos.style_urls")),
    path("artworks/", include("apps.artworks.urls")),
    path("gallery/", include("apps.gallery.urls")),
    path("about/", include("apps.artists.urls")),
    path("booking/", include("apps.booking.urls")),
    path("shop/", include("apps.shop.urls")),
    path("contact/", include("apps.contact.urls")),
    path("account/", include("apps.accounts.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # django-debug-toolbar, dev only
    try:
        import debug_toolbar  # noqa: F401

        urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
    except ImportError:
        pass

# Custom error handlers. Both are styled and on-brand; the 500 never leaks a traceback.
handler404 = "apps.core.views.error_404"
handler500 = "apps.core.views.error_500"
