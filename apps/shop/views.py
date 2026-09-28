"""
Shop views.

Honest about availability: sold-out and made-to-order states are stated plainly, and
there is no button that pretends to charge anyone. Checkout lands behind a
PaymentProvider protocol when a provider is configured.
"""

from __future__ import annotations

from django.db.models import Count, Q
from django.views.generic import DetailView, ListView

from apps.core.mixins import MetadataMixin
from services import seo

from .models import Product, ProductCategory


class ProductListView(MetadataMixin, ListView):
    model = Product
    template_name = "pages/shop.html"
    context_object_name = "products"
    paginate_by = 12
    meta_title = "Shop"
    meta_description = (
        "Prints, posters and original artwork. Made-to-order and limited editions."
    )

    def get_queryset(self):
        qs = (
            Product.objects.published()
            .select_related("category")
            .prefetch_related("images__asset", "tags")
        )
        category = self.request.GET.get("category")
        if category:
            qs = qs.filter(category__slug=category)
        ptype = self.request.GET.get("type")
        if ptype:
            qs = qs.filter(product_type=ptype)
        availability = self.request.GET.get("availability")
        if availability:
            qs = qs.filter(availability=availability)
        query = self.request.GET.get("q", "").strip()
        if query:
            qs = qs.filter(Q(name__icontains=query) | Q(description__icontains=query))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_name"] = "shop"
        ctx["categories"] = ProductCategory.objects.annotate(
            product_count=Count("products", filter=Q(products__status="published"))
        ).order_by("order", "name")
        ctx["type_choices"] = Product.Type.choices
        ctx["availability_choices"] = Product.Availability.choices
        ctx["active_filters"] = {
            "category": self.request.GET.get("category", ""),
            "type": self.request.GET.get("type", ""),
            "availability": self.request.GET.get("availability", ""),
            "q": self.request.GET.get("q", ""),
        }
        ctx["has_filters"] = any(ctx["active_filters"].values())
        return ctx


class ProductDetailView(MetadataMixin, DetailView):
    model = Product
    template_name = "pages/product_detail.html"
    context_object_name = "product"

    def get_queryset(self):
        return (
            Product.objects.published()
            .select_related("category")
            .prefetch_related("images__asset", "tags")
        )

    def get_meta_title(self) -> str:
        return getattr(self.object, "name", "Product")

    def get_structured_data(self):
        return [seo.product_schema(self.request, self.object)]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_name"] = "product"
        images = list(self.object.images.select_related("asset"))
        images.sort(key=lambda i: (not i.is_primary, i.order))
        ctx["gallery_images"] = images
        return ctx
