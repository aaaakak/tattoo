"""
Artwork views.

Artwork is presented as a gallery object: medium, dimensions, year, edition and
availability. Never placement or size-on-body, which belong to tattoos.
"""

from __future__ import annotations

from django.db.models import Count, Q
from django.views.generic import DetailView, ListView

from apps.core.mixins import MetadataMixin
from services import seo

from .models import Artwork, ArtworkCategory


class ArtworkListView(MetadataMixin, ListView):
    model = Artwork
    template_name = "pages/artworks_list.html"
    context_object_name = "artworks"
    paginate_by = 12
    meta_title = "Artwork"
    meta_description = (
        "Paintings, drawings, illustration and digital work — the practice "
        "beyond tattoo."
    )

    def get_queryset(self):
        qs = (
            Artwork.objects.published()
            .select_related("category")
            .prefetch_related("images__asset", "tags")
        )

        category = self.request.GET.get("category")
        if category:
            qs = qs.filter(category__slug=category)

        year = self.request.GET.get("year")
        if year and str(year).isdigit():
            qs = qs.filter(year=int(year))

        availability = self.request.GET.get("availability")
        if availability:
            qs = qs.filter(availability=availability)

        query = self.request.GET.get("q", "").strip()
        if query:
            qs = qs.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(medium__icontains=query)
            )

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_name"] = "artworks"
        ctx["categories"] = ArtworkCategory.objects.annotate(
            work_count=Count("artworks", filter=Q(artworks__status="published"))
        ).order_by("order", "name")
        ctx["years"] = (
            Artwork.objects.published()
            .exclude(year__isnull=True)
            .values_list("year", flat=True)
            .distinct()
            .order_by("-year")
        )
        ctx["availability_choices"] = Artwork.Availability.choices
        ctx["active_filters"] = {
            "category": self.request.GET.get("category", ""),
            "year": self.request.GET.get("year", ""),
            "availability": self.request.GET.get("availability", ""),
            "q": self.request.GET.get("q", ""),
        }
        ctx["has_filters"] = any(ctx["active_filters"].values())
        return ctx


class ArtworkDetailView(MetadataMixin, DetailView):
    model = Artwork
    template_name = "pages/artwork_detail.html"
    context_object_name = "artwork"

    def get_queryset(self):
        return (
            Artwork.objects.published()
            .select_related("category")
            .prefetch_related("images__asset", "tags")
        )

    def get_meta_title(self) -> str:
        return getattr(self.object, "title", "Artwork")

    def get_structured_data(self):
        return [seo.creative_work_schema(self.request, self.object, kind="VisualArtwork")]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_name"] = "artwork"
        images = list(self.object.images.select_related("asset"))
        images.sort(key=lambda i: (not i.is_primary, i.order))
        ctx["gallery_images"] = images
        ctx["related"] = (
            Artwork.objects.published()
            .filter(category=self.object.category)
            .exclude(pk=self.object.pk)
            .prefetch_related("images__asset")
            .distinct()[:3]
        )
        # Reuse the tattoo lightbox builder: the payload shape must be identical so the
        # viewer component has one contract, not one per content type.
        from apps.tattoos.views import _lightbox_items

        ctx["lightbox_items"] = _lightbox_items(
            images, title=self.object.title, meta=self.object.medium
        )
        return ctx


class CategoryDetailView(MetadataMixin, DetailView):
    model = ArtworkCategory
    template_name = "pages/artwork_category.html"
    context_object_name = "category"

    def get_meta_title(self) -> str:
        return f"{self.object.name}" if self.object else "Category"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_name"] = "artwork_category"
        ctx["artworks"] = (
            self.object.artworks.filter(status="published")
            .prefetch_related("images__asset")[:24]
        )
        return ctx

