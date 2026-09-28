"""
Admin for contact messages: a simple inbound queue.

The only real requirement is that unread messages are obvious and can be marked read
quickly, because a portfolio site's contact form is otherwise easy to forget.
"""

from __future__ import annotations

from django.contrib import admin
from django.utils import timezone

from .models import ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "subject", "read_state", "created_at", "replied_at")
    list_filter = ("is_read", "created_at")
    search_fields = ("name", "email", "subject", "message")
    readonly_fields = ("name", "email", "phone", "subject", "message", "created_at")
    date_hierarchy = "created_at"
    actions = ("action_mark_read", "action_mark_replied")
    list_per_page = 40

    fieldsets = (
        ("Message", {"fields": ("name", "email", "phone", "subject", "message", "created_at")}),
        ("Handling", {"fields": ("is_read", "replied_at")}),
    )

    @admin.display(description="status", ordering="is_read")
    def read_state(self, obj):
        if obj.replied_at:
            return "Replied"
        return "Unread" if not obj.is_read else "Read"

    @admin.action(description="Mark selected as read")
    def action_mark_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, f"Marked {updated} message(s) as read.")

    @admin.action(description="Mark selected as replied")
    def action_mark_replied(self, request, queryset):
        updated = queryset.update(is_read=True, replied_at=timezone.now())
        self.message_user(request, f"Marked {updated} message(s) as replied.")
