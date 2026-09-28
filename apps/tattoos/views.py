"""
Tattoo views: portfolio list, detail, style index and style detail.

Filtering is link-based (query parameters), never JS-only, so every filtered view is
shareable, bookmarkable and indexable — and works with JavaScript disabled.
"""

from __future__ import annotations

from django.db.models import Count, Q
from django.views.generic import DetailView, ListView

from apps.core.mixins import MetadataMixin
from services import seo

from .models import Tattoo, TattooStyle


class TattooListView(MetadataMixin, ListView):
    model = Tattoo
    template_name = "pages/tattoos_list.html"
    context_object_name = "tattoos"
    paginate_by = 12
    meta_title = "Tattoos"
    meta_description = (
        "Tattoo work: blackwork, gothic, ornamental and geometric pieces, "
        "with placement, size and session detail for each."
    )

    def get_queryset(self):
        qs = (
            Tattoo.objects.published()
            .prefetch_related("styles", "images__asset", "tags")
        )

        style = self.request.GET.get("style")
        if style:
            qs = qs.filter(styles__slug=style)

        placement = self.request.GET.get("placement")
        if placement:
            qs = qs.filter(placement__iexact=placement)

        colour = self.request.GET.get("colour")
        if colour == "black":
            qs = qs.filter(is_color=False)
        elif colour == "colour":
            qs = qs.filter(is_color=True)

        query = self.request.GET.get("q", "").strip()
        if query:
            qs = qs.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(placement__icontains=query)
                | Q(tags__name__icontains=query)
            )

        return qs.distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_name"] = "tattoos"
        ctx["styles"] = TattooStyle.objects.annotate(
            piece_count=Count("tattoos", filter=Q(tattoos__status="published"))
        ).order_by("order", "name")
        ctx["placements"] = (
            Tattoo.objects.published()
            .exclude(placement="")
            .values_list("placement", flat=True)
            .distinct()
            .order_by("placement")
        )
        ctx["active_filters"] = {
            "style": self.request.GET.get("style", ""),
            "placement": self.request.GET.get("placement", ""),
            "colour": self.request.GET.get("colour", ""),
            "q": self.request.GET.get("q", ""),
        }
        ctx["has_filters"] = any(ctx["active_filters"].values())
        return ctx

    def get_structured_data(self):
        return [seo.person_schema(self.request, self._artist(), self._site())]

    def _artist(self):
        from apps.artists.models import ArtistProfile

        return ArtistProfile.load()

    def _site(self):
        from apps.core.models import SiteSettings

        return SiteSettings.load()


class TattooDetailView(MetadataMixin, DetailView):
    model = Tattoo
    template_name = "pages/tattoo_detail.html"
    context_object_name = "tattoo"

    def get_queryset(self):
        return (
            Tattoo.objects.published()
            .prefetch_related("styles", "images__asset", "tags")
        )

    def get_meta_title(self) -> str:
        return getattr(self.object, "title", "Tattoo")

    def get_structured_data(self):
        return [
            seo.creative_work_schema(
                self.request, self.object, kind="VisualArtwork"
            )
        ]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_name"] = "tattoo"
        style_ids = self.object.styles.values_list("id", flat=True)
        ctx["related"] = (
            Tattoo.objects.published()
            .filter(styles__id__in=style_ids)
            .exclude(pk=self.object.pk)
            .prefetch_related("images__asset", "styles")
            .distinct()[:4]
        )
        # Additional images for the lightbox, primary first.
        images = list(self.object.images.select_related("asset"))
        images.sort(key=lambda i: (not i.is_primary, i.order))
        ctx["gallery_images"] = images
        ctx["lightbox_items"] = _lightbox_items(images, title=self.object.title,
                                                meta=self.object.placement)
        return ctx


class StyleListView(MetadataMixin, ListView):
    model = TattooStyle
    template_name = "pages/styles_list.html"
    context_object_name = "styles"
    meta_title = "Tattoo styles"
    meta_description = (
        "The styles practised: blackwork, fine line, gothic, ornamental, geometric "
        "and custom work."
    )

    def get_queryset(self):
        return TattooStyle.objects.annotate(
            piece_count=Count("tattoos", filter=Q(tattoos__status="published"))
        ).order_by("order", "name")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_name"] = "styles"
        return ctx


class StyleDetailView(MetadataMixin, DetailView):
    model = TattooStyle
    template_name = "pages/style_detail.html"
    context_object_name = "style"

    def get_meta_title(self) -> str:
        return f"{self.object.name} tattoos" if self.object else "Style"

    def get_meta_description(self) -> str:
        return getattr(self.object, "description", "") or ""

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_name"] = "style"
        ctx["tattoos"] = (
            self.object.tattoos.filter(status="published")
            .prefetch_related("images__asset", "styles")[:24]
        )
        return ctx


def _lightbox_items(images, *, title: str = "", meta: str = "") -> list[dict]:
    """
    Build the lightbox payload for an image set.

    Returned as plain dicts so the template does not walk two model shapes, and so the
    JSON handed to the viewer is uniform between tattoos, artworks and the gallery.
    """
    from apps.core.models import MediaAsset

    items = []
    for img in images:
        asset = getattr(img, "asset", None)
        if not asset or not asset.file:
            continue
        dither = ""
        if asset.sha256:
            sibling = MediaAsset.objects.filter(
                sha256=asset.sha256, kind=MediaAsset.Kind.DITHER
            ).first()
            if sibling and sibling.file:
                dither = sibling.file.url
        items.append({
            "url": asset.file.url,
            "dither": dither,
            "title": img.caption or title,
            "meta": meta,
            "href": "",
            "alt": img.caption or title,
            "ratio": f"{asset.width} / {asset.height}",
        })
    return items
