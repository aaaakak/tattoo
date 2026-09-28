"""
Contact view.

Phase 7 adds message submission. The GET path already renders the real editorial layout:
contact channels, studio location and working hours derived from Availability, so the
site can never contradict the booking system.
"""

from __future__ import annotations

from django.views.generic import TemplateView

from apps.core.mixins import MetadataMixin


class ContactView(MetadataMixin, TemplateView):
    template_name = "pages/contact.html"
    meta_title = "Contact"
    meta_description = "Instagram, Telegram, email, phone and studio location."

    def get_context_data(self, **kwargs):
        from apps.booking.models import Availability
        from apps.core.models import SocialLink

        ctx = super().get_context_data(**kwargs)
        ctx["page_name"] = "contact"
        ctx["social_links"] = SocialLink.objects.filter(is_active=True).order_by("order", "label")
        # Working hours come from Availability, never typed twice.
        ctx["working_hours"] = Availability.objects.filter(is_active=True).order_by("weekday", "start_time")
        return ctx
