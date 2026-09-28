"""
Admin for core: MediaAsset, Tag, SiteSettings, SocialLink.

SiteSettings and ArtistProfile are singletons. Their admin must prevent add/delete — the
artist edits one existing record, and the singleton model already enforces pk=1 at the
database level, so the admin should make that visible rather than offer buttons that fail.
"""

from __future__ import annotations

from django.contrib import admin
from django.utils.html import format_html

from .models import MediaAsset, SiteSettings, SocialLink, Tag


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = ("thumb", "kind", "variant_key", "dimensions", "size_kb", "dither_threshold", "created_at")
    list_filter = ("kind", "created_at")
    search_fields = ("alt_text", "file", "sha256")
    readonly_fields = ("sha256", "width", "height", "byte_size", "preview", "variants_summary")
    date_hierarchy = "created_at"
    list_per_page = 50

    fieldsets = (
        ("File", {"fields": ("file", "kind", "variant_key", "preview")}),
        ("Metadata", {"fields": ("alt_text", "width", "height", "byte_size", "sha256")}),
        (
            "Dither generation",
            {
                "fields": ("dither_threshold", "dither_width"),
                "description": (
                    "The halftone cutoff is PER IMAGE, not global. Lower values keep fine "
                    "linework legible on paper-ground artwork; raise it for dark-ground "
                    "pieces or they crush into solid blocks. Changing these does not "
                    "regenerate existing plates."
                ),
            },
        ),
        ("Variants", {"fields": ("variants_summary",)}),
    )

    @admin.display(description="preview")
    def thumb(self, obj):
        if not obj.file:
            return "—"
        return format_html(
            '<img src="{}" style="height:44px;width:44px;object-fit:cover;'
            'border:1px solid #333;background:#111">',
            obj.file.url,
        )

    @admin.display(description="preview")
    def preview(self, obj):
        if not obj.file:
            return "—"
        return format_html(
            '<img src="{}" style="max-height:280px;border:1px solid #333;background:#111">',
            obj.file.url,
        )

    @admin.display(description="dimensions")
    def dimensions(self, obj):
        return f"{obj.width} × {obj.height}" if obj.width else "—"

    @admin.display(description="size")
    def size_kb(self, obj):
        return f"{obj.byte_size / 1024:.0f} KB" if obj.byte_size else "—"

    @admin.display(description="sibling variants")
    def variants_summary(self, obj):
        if not obj.sha256:
            return "—"
        siblings = MediaAsset.objects.filter(sha256=obj.sha256).exclude(pk=obj.pk)
        if not siblings.exists():
            return "None generated yet."
        rows = "".join(
            f"<li>{s.kind} <code>{s.variant_key or '-'}</code> — {s.width}×{s.height}</li>"
            for s in siblings.order_by("kind", "variant_key")
        )
        return format_html("<ul style='margin:0;padding-left:1.2em'>{}</ul>", format_html(rows))


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "kind")
    list_filter = ("kind",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(SocialLink)
class SocialLinkAdmin(admin.ModelAdmin):
    list_display = ("platform", "label", "url", "order", "is_active")
    list_filter = ("platform", "is_active")
    list_editable = ("order", "is_active")
    search_fields = ("label", "handle", "url")
    ordering = ("order",)


class SingletonAdmin(admin.ModelAdmin):
    """
    Base for singleton content.

    Hides add/delete and short-circuits the changelist into the single record, because a
    singleton has exactly one row by design and offering "Add" produces a confusing
    IntegrityError instead of a useful action.
    """

    save_on_top = True

    def has_add_permission(self, request):
        return not self.model.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        """Redirect the list straight to the one object so there is no confusing table."""
        obj = self.model.objects.first()
        if obj is not None:
            from django.shortcuts import redirect
            from django.urls import reverse

            return redirect(
                reverse(f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_change",
                        args=[obj.pk])
            )
        return super().changelist_view(request, extra_context)


@admin.register(SiteSettings)
class SiteSettingsAdmin(SingletonAdmin):
    fieldsets = (
        ("Identity", {"fields": ("site_name", "tagline")}),
        (
            "Hero",
            {
                "fields": ("hero_kicker", "hero_title", "hero_media"),
                "description": (
                    "The hero headline respects line breaks — each line becomes its own "
                    "masked reveal. Use one line per word group for the intended effect."
                ),
            },
        ),
        ("SEO defaults", {"fields": ("default_meta_description", "og_default_image")}),
        ("Contact", {"fields": ("contact_email", "contact_phone", "studio_address", "map_embed_url")}),
        ("Booking", {"fields": ("booking_open", "announcement")}),
    )

    @admin.display(description="hero preview")
    def hero_preview(self, obj):
        if not obj.hero_media:
            return "No hero image set."
        return format_html('<img src="{}" style="max-height:200px">', obj.hero_media.file.url)
