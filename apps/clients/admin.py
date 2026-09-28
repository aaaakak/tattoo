"""
Admin for clients.

Deliberately light. A client record exists to answer three questions: who is this, what
have they had done, and what should I remember about them. Anything beyond that is
over-engineering a one-person studio.
"""

from __future__ import annotations

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "booking_count", "is_vip", "created_at")
    list_filter = ("is_vip", "created_at", "tags")
    search_fields = ("name", "email", "phone", "instagram", "telegram", "notes")
    filter_horizontal = ("tags",)
    readonly_fields = ("slug", "created_at", "updated_at", "booking_history")
    date_hierarchy = "created_at"

    fieldsets = (
        ("Identity", {"fields": ("name", "slug")}),
        ("Contact", {"fields": ("email", "phone", "instagram", "telegram")}),
        ("Artist notes", {"fields": ("notes", "preferences", "is_vip", "tags")}),
        ("History", {"fields": ("booking_history",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="bookings")
    def booking_count(self, obj):
        return obj.bookings.count()

    @admin.display(description="booking history")
    def booking_history(self, obj):
        if not obj.pk:
            return "Save the client first."
        bookings = obj.bookings.order_by("-created_at")
        if not bookings.exists():
            return "No bookings yet."
        rows = []
        for b in bookings:
            url = reverse("admin:booking_booking_change", args=[b.pk])
            rows.append(
                f'<li><a href="{url}"><code>{b.reference}</code></a> — '
                f"{b.get_status_display()} — {b.created_at:%Y-%m-%d}</li>"
            )
        return format_html("<ul style='margin:0;padding-left:1.2em'>{}</ul>", format_html("".join(rows)))
