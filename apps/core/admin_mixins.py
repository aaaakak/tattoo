"""
Shared admin building blocks.

Registered as mixins and inlines so the five content apps (tattoos, artworks, gallery,
shop, core) present a consistent, learned-once interface. Without this, each app's admin
drifts and the artist has to relearn the CMS for every content type.
"""

from __future__ import annotations

from django.contrib import admin
from django.utils.html import format_html


class PublishedAdminMixin:
    """
    Common controls for the content models that share PublishableModel.

    Exposes status and featured as inline-editable list columns so the artist can publish
    and feature work from the changelist without opening each record.
    """

    list_editable = ("status", "is_featured")
    list_filter = ("status", "is_featured")
    date_hierarchy = "created_at"
    save_on_top = True
    actions = ("action_publish", "action_unpublish", "action_feature", "action_unfeature")

    @admin.action(description="Publish selected items")
    def action_publish(self, request, queryset):
        for obj in queryset:
            obj.publish()
        self.message_user(request, f"Published {queryset.count()} item(s).")

    @admin.action(description="Unpublish selected items")
    def action_unpublish(self, request, queryset):
        updated = queryset.update(status="draft")
        self.message_user(request, f"Moved {updated} item(s) back to draft.")

    @admin.action(description="Mark selected as featured")
    def action_feature(self, request, queryset):
        updated = queryset.update(is_featured=True)
        self.message_user(request, f"Featured {updated} item(s).")

    @admin.action(description="Remove featured flag")
    def action_unfeature(self, request, queryset):
        updated = queryset.update(is_featured=False)
        self.message_user(request, f"Unfeatured {updated} item(s).")


@admin.display(description="content", ordering="is_placeholder")
def placeholder_column(obj) -> str:
    """
    Visible marker for demonstration content, so generated sample work can never be
    mistaken for the artist's real work. Used as a `list_display` entry.

    CRITICAL — why this is a staticmethod:

    Django's changelist resolves each `list_display` entry via `lookup_field`, which
    fetches the attribute from the admin *instance*. A plain module-level function
    assigned as a class attribute becomes a bound method and is then called with
    (self, obj) — raising "takes 1 positional argument but 2 were given" and returning a
    500 on the changelist.

    A unit test that calls the function directly will NOT catch this: it passes while the
    real admin page crashes. The staticmethod prevents the binding entirely, and
    `tests/test_admin.py::test_content_changelists_load` covers the real HTTP path.

    Declared with @admin.display directly (not wrapped after the fact) so the description
    and ordering survive the staticmethod decoration.
    """
    if getattr(obj, "is_placeholder", False):
        return format_html(
            '<span style="color:#B45309;font-weight:600" title="Demonstration content">'
            "PLACEHOLDER</span>"
        )
    return "—"


# staticmethod must be applied outermost: admin.display returns an AdminDisplay object,
# and binding that as a class attribute would otherwise still inject `self`.
placeholder_column = staticmethod(placeholder_column)


def primary_image_of(obj):
    """Resolve a primary image asset for the changelist thumbnail."""
    getter = getattr(obj, "primary_image", None)
    return getter() if callable(getter) else getter
