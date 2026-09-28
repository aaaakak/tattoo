"""
Sitemaps for the indexable surfaces.

Drafts, confirmation pages and the design-system reference are deliberately excluded --
indexing them would be a correctness bug, not just noise.
"""

from __future__ import annotations

from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    priority = 0.6
    changefreq = "weekly"

    def items(self):
        return [
            "core:home",
            "tattoos:list",
            "styles:index",
            "artworks:list",
            "gallery:index",
            "artists:about",
            "shop:list",
            "contact:index",
            "booking:create",
        ]

    def location(self, item):
        return reverse(item)


class TattooSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.8

    def items(self):
        from apps.tattoos.models import Tattoo

        return Tattoo.objects.published().order_by("-published_at")

    def lastmod(self, obj):
        return obj.updated_at


class TattooStyleSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.7

    def items(self):
        from apps.tattoos.models import TattooStyle

        return TattooStyle.objects.order_by("order")

    def location(self, obj):
        return obj.get_absolute_url()


class ArtworkSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.8

    def items(self):
        from apps.artworks.models import Artwork

        return Artwork.objects.published().order_by("-published_at")

    def lastmod(self, obj):
        return obj.updated_at


class ArtworkCategorySitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        from apps.artworks.models import ArtworkCategory

        return ArtworkCategory.objects.order_by("order")

    def location(self, obj):
        return obj.get_absolute_url()


class GalleryCollectionSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        from apps.gallery.models import GalleryCollection

        return GalleryCollection.objects.order_by("order")

    def location(self, obj):
        return obj.get_absolute_url()


class ProductSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        from apps.shop.models import Product

        return Product.objects.published().order_by("-created_at")

    def lastmod(self, obj):
        return obj.updated_at
