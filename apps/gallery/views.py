"""
Gallery views.

The gallery is a CURATION layer: GalleryImage references an existing TattooImage or
ArtworkImage for provenance and adds layout metadata (aspect, span, order). Until
curation is authored, featured tattoo and artwork imagery is surfaced so the page is
never empty.
"""

from __future__ import annotations

from django.views.generic import DetailView, ListView

from apps.core.mixins import MetadataMixin
from apps.core.models import MediaAsset

from .models import GalleryCollection, GalleryImage


def _lightbox_items(tattoos, artworks):
    """
    Build the lightbox payload: one entry per image with its display metadata.

    Returned as a plain list of dicts so the template does not have to walk two different
    model shapes, and so the JSON handed to the viewer is uniform.
    """
    items = []
    for tattoo in tattoos:
        for img in tattoo.images.all():
            items.append({
                "url": img.asset.file.url if img.asset and img.asset.file else "",
                "dither": _dither_url(img.asset),
                "title": tattoo.title,
                "meta": tattoo.placement or "",
                "href": tattoo.get_absolute_url(),
                "alt": img.caption or tattoo.title,
                "ratio": f"{img.asset.width} / {img.asset.height}" if img.asset else "4 / 5",
            })
    for artwork in artworks:
        for img in artwork.images.all():
            items.append({
                "url": img.asset.file.url if img.asset and img.asset.file else "",
                "dither": _dither_url(img.asset),
                "title": artwork.title,
                "meta": artwork.medium or "",
                "href": artwork.get_absolute_url(),
                "alt": img.caption or artwork.title,
                "ratio": f"{img.asset.width} / {img.asset.height}" if img.asset else "4 / 5",
            })
    return [i for i in items if i["url"]]


def _dither_url(asset):
    """Resolve the dither sibling for an asset, if one was generated."""
    if not asset or not asset.sha256:
        return ""
    sibling = MediaAsset.objects.filter(
        sha256=asset.sha256, kind=MediaAsset.Kind.DITHER
    ).first()
    return sibling.file.url if sibling and sibling.file else ""


class GalleryView(MetadataMixin, ListView):
    model = GalleryImage
    template_name = "pages/gallery.html"
    context_object_name = "images"
    paginate_by = 24
    meta_title = "Gallery"
    meta_description = (
        "An archive of tattoo work, drawings and digital pieces — "
        "curated sets and full-screen viewing."
    )

    def get_queryset(self):
        qs = (
            GalleryImage.objects.select_related("asset", "collection")
            .order_by("order", "id")
        )
        collection = self.request.GET.get("collection")
        if collection:
            qs = qs.filter(collection__slug=collection)
        if self.request.GET.get("featured") == "1":
            qs = qs.filter(is_featured=True)
        return qs

    def get_context_data(self, **kwargs):
        from apps.artworks.models import Artwork
        from apps.tattoos.models import Tattoo

        ctx = super().get_context_data(**kwargs)
        ctx["page_name"] = "gallery"
        ctx["collections"] = GalleryCollection.objects.order_by("order", "title")

        # Curated GalleryImage rows take precedence; curated content is the artist's intent.
        if self.get_queryset().exists():
            ctx["featured_tattoos"] = []
            ctx["featured_artworks"] = []
            ctx["lightbox_items"] = []
        else:
            tattoos = list(
                Tattoo.objects.published()
                .filter(is_featured=True)
                .prefetch_related("images__asset", "styles")[:6]
            )
            artworks = list(
                Artwork.objects.published()
                .filter(is_featured=True)
                .prefetch_related("images__asset")[:3]
            )
            ctx["featured_tattoos"] = tattoos
            ctx["featured_artworks"] = artworks
            ctx["lightbox_items"] = _lightbox_items(tattoos, artworks)

        ctx["active_filters"] = {
            "collection": self.request.GET.get("collection", ""),
            "featured": self.request.GET.get("featured", ""),
        }
        return ctx


class CollectionDetailView(MetadataMixin, DetailView):
    model = GalleryCollection
    template_name = "pages/gallery_collection.html"
    context_object_name = "collection"

    def get_meta_title(self) -> str:
        return getattr(self.object, "title", "Collection")

    def get_meta_description(self) -> str:
        return getattr(self.object, "description", "") or ""

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_name"] = "gallery_collection"
        images = list(self.object.images.select_related("asset")[:48])
        ctx["images"] = images
        ctx["lightbox_items"] = [
            {
                "url": i.asset.file.url if i.asset and i.asset.file else "",
                "dither": _dither_url(i.asset),
                "title": i.caption or self.object.title,
                "meta": "",
                "href": "",
                "alt": i.caption or self.object.title,
                "ratio": f"{i.asset.width} / {i.asset.height}" if i.asset else "4 / 5",
            }
            for i in images
            if i.asset and i.asset.file
        ]
        return ctx
