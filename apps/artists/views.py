"""
Artist / about view.

An editorial page: statement, portrait, biography, practice, statistics, location.
"""

from __future__ import annotations

from django.views.generic import TemplateView

from apps.core.mixins import MetadataMixin
from services import seo


class AboutView(MetadataMixin, TemplateView):
    template_name = "pages/about.html"
    meta_title = "About"

    def get_meta_description(self) -> str:
        from apps.artists.models import ArtistProfile

        artist = ArtistProfile.load()
        if artist and artist.statement:
            return artist.statement
        return "The artist's practice, statement and studio."

    def get_structured_data(self):
        from apps.artists.models import ArtistProfile
        from apps.core.models import SiteSettings

        return [seo.person_schema(self.request, ArtistProfile.load(), SiteSettings.load())]

    def get_context_data(self, **kwargs):
        from apps.core.models import SocialLink
        from apps.tattoos.models import TattooStyle

        ctx = super().get_context_data(**kwargs)
        ctx["page_name"] = "about"
        ctx["social_links"] = SocialLink.objects.filter(is_active=True).order_by("order", "label")
        ctx["styles"] = TattooStyle.objects.order_by("order", "name")
        return ctx
