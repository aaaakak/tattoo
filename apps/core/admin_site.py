"""
Custom admin site.

Two jobs:

  1. Rebrand the chrome so the artist sees their studio, not "Django administration".
  2. Put a working dashboard on the index: open bookings, unread messages, low stock and
     publication counts. The default admin index is a list of model names, which tells
     the artist nothing about what needs attention today.

The dashboard queries are written to be cheap: aggregate counts and a handful of
limited rows, never a full table scan rendered into a template.
"""

from __future__ import annotations

from django.contrib import admin


class TattoWebAdminSite(admin.AdminSite):
    site_header = "STUDIO ADMINISTRATION"
    site_title = "Studio"
    index_title = "Overview"
    empty_value_display = "—"

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context.update(self._dashboard())
        return super().index(request, extra_context)

    @staticmethod
    def _dashboard() -> dict:
        """
        Build the dashboard payload.

        Wrapped in broad exception handling on purpose: the dashboard must never be the
        reason the artist cannot reach the admin. A missing table or an empty database
        degrades to zeros rather than a 500.
        """
        data: dict = {
            "stats": [],
            "open_bookings": [],
            "unread_messages": 0,
            "low_stock": [],
            "draft_count": 0,
        }
        try:
            from apps.artworks.models import Artwork
            from apps.booking.models import Booking
            from apps.clients.models import Client
            from apps.contact.models import ContactMessage
            from apps.shop.models import Product
            from apps.tattoos.models import Tattoo

            open_statuses = [
                Booking.Status.NEW,
                Booking.Status.REVIEWING,
                Booking.Status.POTENTIAL,
                Booking.Status.APPROVED,
            ]

            data["stats"] = [
                {"label": "OPEN BOOKINGS", "value": Booking.objects.filter(status__in=open_statuses).count()},
                {"label": "SCHEDULED", "value": Booking.objects.filter(status=Booking.Status.SCHEDULED).count()},
                {"label": "CLIENTS", "value": Client.objects.count()},
                {"label": "PUBLISHED TATTOOS", "value": Tattoo.objects.filter(status="published").count()},
                {"label": "PUBLISHED ARTWORK", "value": Artwork.objects.filter(status="published").count()},
                {"label": "UNREAD MESSAGES", "value": ContactMessage.objects.filter(is_read=False).count()},
            ]

            data["open_bookings"] = list(
                Booking.objects.filter(status__in=open_statuses)
                .select_related("client", "style")
                .order_by("-created_at")[:8]
            )

            data["unread_messages"] = ContactMessage.objects.filter(is_read=False).count()

            # Low stock: real products only, excluding made-to-order (stock is NULL).
            data["low_stock"] = list(
                Product.objects.filter(stock__isnull=False, stock__lte=3, status="published")
                .order_by("stock")[:6]
            )

            data["draft_count"] = (
                Tattoo.objects.filter(status="draft").count()
                + Artwork.objects.filter(status="draft").count()
                + Product.objects.filter(status="draft").count()
            )
        except Exception:
            pass
        return data

    def get_app_list(self, request, app_label=None):
        """
        Order the app index by workflow, not alphabetically.

        The artist's day runs: content → people → commerce → reference. That is the order
        they should see, not 'artists, artworks, booking, clients…'.
        """
        ordering = [
            "core", "artists", "tattoos", "artworks", "gallery",
            "booking", "clients", "shop", "contact",
        ]
        app_list = super().get_app_list(request, app_label)
        return sorted(app_list, key=lambda a: ordering.index(a["app_label"])
                      if a["app_label"] in ordering else len(ordering))
