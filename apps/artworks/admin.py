"""
Admin for artworks.

Deliberately mirrors the tattoo admin's structure so the artist learns one interface, but
the fields differ where the domain differs: medium, dimensions, year, edition and
availability — never placement or size-on-body.
"""

from __future__ import annotations

from django.contrib import admin
from django.utils.html import format_html

from apps.core.admin_mixins import (
    PublishedAdminMixin,
    SimpleImageUploadMixin,
    placeholder_column,
)

from .models import Artwork, ArtworkCategory, ArtworkImage


@admin.register(ArtworkCategory)
class ArtworkCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "work_count", "is_featured", "order")
    list_editable = ("is_featured", "order")
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("order", "name")

    @admin.display(description="works")
    def work_count(self, obj):
        return obj.artworks.filter(status="published").count()


class ArtworkImageInline(admin.TabularInline):
    model = ArtworkImage
    # extra = 0: a fresh artwork form shows ONE upload box (the `upload_image` field below),
    # not an empty inline row competing with it. The inline stays for attaching extra images
    # to an artwork that already exists.
    extra = 0
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


@admin.register(Artwork)
class ArtworkAdmin(SimpleImageUploadMixin, PublishedAdminMixin, admin.ModelAdmin):
    """Normal Django admin: fill the fields, drop in an image, save."""

    image_rel_name = "images"
    image_model = ArtworkImage
    image_fk_name = "artwork"
    image_upload_label = "Artwork image"

    list_display = (
        "thumb", "title", "category", "medium", "year",
        "availability", "placeholder_column", "is_featured", "status",
    )
    list_filter = ("status", "is_featured", "is_placeholder", "availability", "category", "year")
    search_fields = ("title", "slug", "description", "medium", "dimensions")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("category", "tags")
    filter_horizontal = ("tags",)
    inlines = [ArtworkImageInline]
    readonly_fields = ("created_at", "updated_at", "primary_preview")
    date_hierarchy = "published_at"
    placeholder_column = placeholder_column
    list_editable = ("is_featured", "status")

    fieldsets = (
        ("Work", {"fields": ("title", "slug", "description")}),
        ("Classification", {"fields": ("category", "tags")}),
        (
            "Physical",
            {
                "fields": ("medium", "dimensions", "year", "edition_info"),
                "description": "Artwork is a gallery object: medium and dimensions, not placement.",
            },
        ),
        ("Availability and price", {"fields": ("availability", "price", "currency")}),
        ("Publication", {"fields": ("status", "published_at", "is_featured", "is_placeholder")}),
        ("Preview", {"fields": ("primary_preview",)}),
        ("SEO", {"fields": ("meta_title", "meta_description"), "classes": ("collapse",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


    @admin.display(description="preview")
    def thumb(self, obj):
        img = obj.primary_image
        if not img or not img.asset.file:
            return "—"
        return format_html(
            '<img src="{}" style="height:56px;border:1px solid #333;background:#111">',
            img.asset.file.url,
        )

    @admin.display(description="primary image")
    def primary_preview(self, obj):
        img = obj.primary_image
        if not img:
            return "No images attached yet."
        return format_html('<img src="{}" style="max-height:300px;border:1px solid #333">', img.asset.file.url)


@admin.register(ArtworkImage)
class ArtworkImageAdmin(admin.ModelAdmin):
    """
    Hidden from non-superusers. Images are attached by uploading on the Artwork form or
    through the inline, so this standalone view is plumbing the artist should not have to
    navigate. Kept for superusers to inspect or repair a link.
    """

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    list_display = ("thumbnail", "artwork", "order", "is_primary", "caption")
    list_filter = ("is_primary",)
    search_fields = ("caption", "artwork__title", "asset__alt_text")
    autocomplete_fields = ("artwork", "asset")
    ordering = ("artwork", "order")

    @admin.display(description="preview")
    def thumbnail(self, obj):
        if not obj.asset or not obj.asset.file:
            return "—"
        return format_html(
            '<img src="{}" style="height:52px;border:1px solid #333;background:#111">',
            obj.asset.file.url,
        )
