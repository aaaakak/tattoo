"""
Admin for the gallery curation layer.

GalleryImage references either a TattooImage or an ArtworkImage through nullable
one-to-one links. The database enforces that at most ONE provenance is set, so the admin
form explains the rule rather than letting the artist discover it as an IntegrityError.
"""

from __future__ import annotations

from django.contrib import admin
from django.utils.html import format_html

from .models import GalleryCollection, GalleryImage


@admin.register(GalleryCollection)
class GalleryCollectionAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "image_count", "is_featured", "order")
    list_editable = ("is_featured", "order")
    search_fields = ("title", "description")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("order", "title")

    @admin.display(description="images")
    def image_count(self, obj):
        return obj.images.count()


@admin.register(GalleryImage)
class GalleryImageAdmin(admin.ModelAdmin):
    list_display = ("thumb", "caption", "collection", "aspect", "span", "is_featured", "order")
    list_filter = ("is_featured", "aspect", "collection")
    list_editable = ("span", "is_featured", "order")
    autocomplete_fields = ("asset", "collection", "tattoo_image", "artwork_image")
    search_fields = ("caption",)
    ordering = ("order", "id")

    fieldsets = (
        ("Image", {"fields": ("asset", "preview", "caption")}),
        ("Placement in the gallery", {"fields": ("collection", "aspect", "span", "order", "is_featured")}),
        (
            "Provenance (optional)",
            {
                "fields": ("tattoo_image", "artwork_image"),
                "description": (
                    "Where this gallery image originally comes from. Set AT MOST ONE — "
                    "setting both is rejected by the database."
                ),
            },
        ),
    )

    readonly_fields = ("preview",)

    @admin.display(description="preview")
    def thumb(self, obj):
        if not obj.asset or not obj.asset.file:
            return "—"
        return format_html(
            '<img src="{}" style="height:56px;border:1px solid #333;background:#111">',
            obj.asset.file.url,
        )

    @admin.display(description="preview")
    def preview(self, obj):
        if not obj.asset or not obj.asset.file:
            return "—"
        return format_html('<img src="{}" style="max-height:300px;border:1px solid #333">', obj.asset.file.url)
