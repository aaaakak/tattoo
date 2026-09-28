"""
Admin for artists: ArtistProfile (singleton) and Statistic (inline).

The statistics block is edited inline on the profile, because that is how the artist
thinks about it — the numbers belong to the artist, not to a separate list.
"""

from __future__ import annotations

from django.contrib import admin
from django.utils.html import format_html

from apps.core.admin import SingletonAdmin

from .models import ArtistProfile, Statistic


class StatisticInline(admin.TabularInline):
    model = Statistic
    extra = 0
    fields = ("order", "value", "label")
    ordering = ("order",)


@admin.register(ArtistProfile)
class ArtistProfileAdmin(SingletonAdmin):
    list_display = ("display_name", "monogram", "location", "years_experience", "is_booking_open")
    inlines = [StatisticInline]

    fieldsets = (
        ("Identity", {"fields": ("user", "display_name", "monogram", "role_line")}),
        (
            "Statement and biography",
            {
                "fields": ("statement", "biography"),
                "description": (
                    "The statement renders as an editorial headline. In the biography, a "
                    "blank line separates paragraphs; the first paragraph is used as the "
                    "homepage excerpt."
                ),
            },
        ),
        ("Portrait", {"fields": ("portrait", "portrait_preview")}),
        ("Location and experience", {"fields": ("location_city", "location_country", "years_experience")}),
        ("Contact", {"fields": ("email", "phone")}),
        ("Booking", {"fields": ("is_booking_open",)}),
        ("SEO", {"fields": ("meta_title", "meta_description"), "classes": ("collapse",)}),
    )

    readonly_fields = ("portrait_preview",)

    @admin.display(description="preview")
    def portrait_preview(self, obj):
        if not obj.portrait:
            return "No portrait set."
        return format_html('<img src="{}" style="max-height:240px">', obj.portrait.file.url)


@admin.register(Statistic)
class StatisticAdmin(admin.ModelAdmin):
    """
    Also registered standalone for bulk editing.

    `label` leads the list_display rather than `value`, because list_editable cannot
    include the first column (admin.E124) — that column is the link to the change form.
    """

    list_display = ("label", "value", "artist", "order")
    list_editable = ("value", "order")
    list_filter = ("artist",)
    ordering = ("artist", "order")
