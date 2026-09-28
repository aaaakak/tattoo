"""
Core views: home, health probe, design-system reference, and the error handlers.

Home is fully CMS-driven: hero copy, statement, statistics and the featured runs all
come from the database. Nothing business-critical is hard-coded in the template.
"""

from __future__ import annotations

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView

from services import seo

from .mixins import MetadataMixin


class HomeView(MetadataMixin, TemplateView):
    template_name = "pages/home.html"
    meta_title = ""
    meta_description = ""

    def get_meta_title(self) -> str:
        from apps.artists.models import ArtistProfile
        from apps.core.models import SiteSettings

        artist = ArtistProfile.load()
        site = SiteSettings.load()
        if artist and artist.display_name and site:
            return f"{artist.display_name} — {site.tagline or site.site_name}"
        return site.site_name if site else ""

    def get_structured_data(self):
        from apps.artists.models import ArtistProfile
        from apps.core.models import SiteSettings

        return [
            seo.person_schema(self.request, ArtistProfile.load(), SiteSettings.load())
        ]

    def get_context_data(self, **kwargs):
        from apps.artworks.models import Artwork
        from apps.tattoos.models import Tattoo, TattooStyle

        ctx = super().get_context_data(**kwargs)
        ctx["page_name"] = "home"

        featured = list(
            Tattoo.objects.published()
            .filter(is_featured=True)
            .prefetch_related("styles", "images__asset")[:3]
        )
        if not featured:
            featured = list(
                Tattoo.objects.published().prefetch_related("styles", "images__asset")[:3]
            )
        ctx["featured_tattoos"] = featured

        art = list(
            Artwork.objects.published()
            .filter(is_featured=True)
            .select_related("category")
            .prefetch_related("images__asset")[:2]
        )
        if not art:
            art = list(
                Artwork.objects.published()
                .select_related("category")
                .prefetch_related("images__asset")[:2]
            )
        ctx["featured_artworks"] = art

        ctx["styles"] = (
            TattooStyle.objects.filter(is_featured=True).order_by("order")[:8]
            or TattooStyle.objects.order_by("order")[:8]
        )
        return ctx


@require_GET
def healthz(request: HttpRequest) -> JsonResponse:
    """
    Liveness probe. Touches the database so a broken connection is a failed health check
    rather than a 200 that lies.
    """
    from django.db import connection

    db_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        db_ok = False

    payload = {
        "status": "ok" if db_ok else "degraded",
        "database": "ok" if db_ok else "error",
        "debug": settings.DEBUG,
    }
    return JsonResponse(payload, status=200 if db_ok else 503)


@never_cache
@require_GET
def design_system(request: HttpRequest) -> HttpResponse:
    """
    Staff-only visual-system reference page.

    Two independent gates: staff-only (non-staff go to login), and availability controlled
    by DESIGN_SYSTEM_ENABLED which defaults to DEBUG. In production it 404s.
    """
    if not getattr(settings, "DESIGN_SYSTEM_ENABLED", settings.DEBUG):
        raise Http404

    if not request.user.is_authenticated or not request.user.is_staff:
        from django.contrib.auth.views import redirect_to_login

        return redirect_to_login(request.get_full_path())

    return render(request, "pages/design_system.html", {"page_name": "design_system"})


# --------------------------------------------------------------------------------------
# Error handlers
# --------------------------------------------------------------------------------------
def error_404(request, exception=None):
    """Styled 404. Mono marker, oversized type, routes back into the portfolio."""
    return render(request, "404.html", status=404, context={"page_name": "404"})


def error_500(request):
    """Styled 500. Never leaks a stack trace."""
    return render(request, "500.html", status=500, context={"page_name": "500"})


@require_GET
def robots(request: HttpRequest) -> HttpResponse:
    """
    robots.txt.

    Served from a view rather than a static file so the sitemap URL is always absolute
    and correct for the host being served -- a static file gets this wrong behind a proxy.
    """
    lines = [
        "User-agent: *",
        "Allow: /",
        # Never index: forms, confirmation pages, the CMS, or the internal design reference.
        "Disallow: /admin/",
        "Disallow: /account/",
        "Disallow: /booking/success/",
        "Disallow: /booking/api/",
        "Disallow: /design-system/",
        "",
        f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}",
        "",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")
