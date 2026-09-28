"""
Admin for the shop.

Honest about availability: the changelist shows the real stock state rather than an
optimistic badge. There is no checkout, and the admin does not pretend otherwise.
"""

from __future__ import annotations

from django.contrib import admin
from django.utils.html import format_html

from apps.core.admin_mixins import PublishedAdminMixin

from .models import Product, ProductCategory, ProductImage


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_featured", "order")
    list_editable = ("is_featured", "order")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("order", "name")


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    autocomplete_fields = ("asset",)
    fields = ("order", "asset", "thumbnail", "caption", "is_primary")
    readonly_fields = ("thumbnail",)
    ordering = ("order",)

    @admin.display(description="preview")
    def thumbnail(self, obj):
        if not obj.asset or not obj.asset.file:
            return "—"
        return format_html(
            '<img src="{}" style="height:60px;border:1px solid #333;background:#111">',
            obj.asset.file.url,
        )


@admin.register(Product)
class ProductAdmin(PublishedAdminMixin, admin.ModelAdmin):
    list_display = ("thumb", "name", "category", "product_type", "price_display", "stock_state", "is_featured", "status")
    list_filter = ("status", "is_featured", "availability", "product_type", "category", "is_limited")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ("category", "tags")
    filter_horizontal = ("tags",)
    inlines = [ProductImageInline]
    readonly_fields = ("created_at", "updated_at", "orderable_state", "primary_preview")
    list_editable = ("is_featured", "status")

    fieldsets = (
        ("Product", {"fields": ("name", "slug", "description")}),
        ("Classification", {"fields": ("category", "product_type", "tags")}),
        ("Pricing", {"fields": ("price", "currency")}),
        (
            "Stock",
            {
                "fields": ("stock", "is_limited", "edition_size", "availability", "orderable_state"),
                "description": (
                    "Leave stock empty for made-to-order or unlimited items. "
                    "Availability is stated plainly on the site — no manufactured urgency."
                ),
            },
        ),
        ("Publication", {"fields": ("status", "published_at", "is_featured")}),
        ("Preview", {"fields": ("primary_preview",)}),
        ("SEO", {"fields": ("meta_title", "meta_description"), "classes": ("collapse",)}),
    )

    @admin.display(description="preview")
    def thumb(self, obj):
        img = obj.images.filter(is_primary=True).first() or obj.images.first()
        if not img or not img.asset.file:
            return "—"
        return format_html(
            '<img src="{}" style="height:56px;border:1px solid #333;background:#111">',
            img.asset.file.url,
        )

    @admin.display(description="price")
    def price_display(self, obj):
        return f"{obj.price} {obj.currency}"

    @admin.display(description="stock")
    def stock_state(self, obj):
        if obj.availability in ("sold_out", "coming_soon"):
            return obj.get_availability_display()
        if obj.stock is None:
            return "made to order"
        if obj.stock == 0:
            return format_html('<span style="color:#B91C1C">out of stock</span>')
        if obj.stock <= 3:
            return format_html('<span style="color:#B45309">{} left</span>', obj.stock)
        return f"{obj.stock} in stock"

    @admin.display(description="orderable")
    def orderable_state(self, obj):
        return "Yes" if obj.is_orderable else "No — will not accept an order"

    @admin.display(description="primary image")
    def primary_preview(self, obj):
        img = obj.images.filter(is_primary=True).first() or obj.images.first()
        if not img:
            return "No images attached yet."
        return format_html('<img src="{}" style="max-height:300px;border:1px solid #333">', img.asset.file.url)
