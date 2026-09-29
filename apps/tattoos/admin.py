"""
Admin for tattoos: styles, pieces, and their images.

TattooImageInline is the workhorse. Two model-level constraints make the inline safe
without extra validation:

  - uniq_tattooimage_order  — no two images may share an order value
  - uniq_tattoo_primary_image (partial) — at most one is_primary per tattoo

Both are enforced by Postgres, so a mistake surfaces as a clear IntegrityError rather
than silently producing a tattoo with two primary images and an ambiguous thumbnail.
"""

from __future__ import annotations

from django.contrib import admin
from django.utils.html import format_html

from apps.core.admin_mixins import (
    PublishedAdminMixin,
    SimpleImageUploadMixin,
    placeholder_column,
)

from .models import Tattoo, TattooImage, TattooStyle


@admin.register(TattooStyle)
class TattooStyleAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "piece_count", "is_featured", "order")
    list_editable = ("is_featured", "order")
    list_filter = ("is_featured",)
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("order", "name")
    save_on_top = True

    fieldsets = (
        ("Style", {"fields": ("name", "slug", "description")}),
        ("Presentation", {"fields": ("cover", "cover_preview", "is_featured", "order")}),
        ("SEO", {"fields": ("meta_title", "meta_description"), "classes": ("collapse",)}),
    )

    readonly_fields = ("cover_preview",)

    @admin.display(description="pieces")
    def piece_count(self, obj):
        return obj.tattoos.filter(status="published").count()

    @admin.display(description="preview")
    def cover_preview(self, obj):
        if not obj.cover:
            return "No cover set."
        return format_html('<img src="{}" style="max-height:160px">', obj.cover.file.url)


class TattooImageInline(admin.TabularInline):
    """
    Inline image management.

    autocomplete_fields on `asset` is essential: without it Django renders a <select>
    containing every MediaAsset row, which becomes unusable at a few hundred images.
    """

    model = TattooImage
    extra = 0
    autocomplete_fields = ("asset",)
    fields = ("order", "asset", "thumbnail", "variant", "caption", "is_primary")
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


@admin.register(Tattoo)
class TattooAdmin(SimpleImageUploadMixin, PublishedAdminMixin, admin.ModelAdmin):
    """Normal Django admin: fill the fields, drop in an image, save."""

    image_rel_name = "images"
    image_model = TattooImage
    image_fk_name = "tattoo"
    image_upload_label = "Tattoo image"
    list_display = (
        "thumb", "title", "style_list", "placement", "is_color",
        "placeholder_column", "is_featured", "status", "published_at",
    )
    list_filter = ("status", "is_featured", "is_color", "is_placeholder", "styles", "placement")
    search_fields = ("title", "slug", "description", "artist_notes", "placement")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("styles", "tags")
    filter_horizontal = ("tags",)
    inlines = [TattooImageInline]
    readonly_fields = ("created_at", "updated_at", "primary_preview")
    date_hierarchy = "published_at"
    placeholder_column = placeholder_column

    list_editable = ("is_featured", "status")

    fieldsets = (
        ("Piece", {"fields": ("title", "slug", "description", "artist_notes")}),
        ("Classification", {"fields": ("styles", "tags", "is_color")}),
        (
            "Specification",
            {
                "fields": ("placement", "size_cm", "duration_minutes", "session_date"),
                "description": "These become the mono technical metadata on the detail page.",
            },
        ),
        ("Pricing", {"fields": ("price_from", "price_to", "currency")}),
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

    @admin.display(description="styles")
    def style_list(self, obj):
        return ", ".join(obj.style_names) or "—"

    @admin.display(description="primary image")
    def primary_preview(self, obj):
        img = obj.primary_image
        if not img:
            return "No images attached yet."
        return format_html(
            '<figure style="margin:0"><img src="{}" style="max-height:300px;border:1px solid #333">'
            '<figcaption style="font-size:11px">order {} · {}</figcaption></figure>',
            img.asset.file.url,
            img.order,
            img.get_variant_display(),
        )

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        # Keep the style chooser to a sensible size; 12 styles fit, 200 would not.
        if db_field.name == "styles":
            kwargs["queryset"] = TattooStyle.objects.order_by("order", "name")
        return super().formfield_for_manytomany(db_field, request, **kwargs)


@admin.register(TattooImage)
class TattooImageAdmin(admin.ModelAdmin):
    """
    Hidden from non-superusers. Images are attached by uploading on the Tattoo form or
    through the inline; this standalone view is plumbing. Kept for superusers so image
    records remain searchable when reconciling an upload.
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

    list_display = ("thumbnail", "tattoo", "variant", "order", "is_primary", "caption")
    list_filter = ("variant", "is_primary")
    search_fields = ("caption", "tattoo__title", "asset__alt_text")
    autocomplete_fields = ("tattoo", "asset")
    ordering = ("tattoo", "order")
    readonly_fields = ("thumbnail_big",)

    @admin.display(description="preview")
    def thumbnail(self, obj):
        if not obj.asset or not obj.asset.file:
            return "—"
        return format_html(
            '<img src="{}" style="height:52px;border:1px solid #333;background:#111">',
            obj.asset.file.url,
        )

    @admin.display(description="full size")
    def thumbnail_big(self, obj):
        if not obj.asset or not obj.asset.file:
            return "—"
        return format_html('<img src="{}" style="max-height:320px;border:1px solid #333">', obj.asset.file.url)
