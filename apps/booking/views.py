"""
Booking views: the request form, confirmation, and the availability JSON the calendar
widget consumes.

The form is a real POST handler: it works with JavaScript disabled. The calendar is an
enhancement that fetches availability and filters the date input's minimum.
"""

from __future__ import annotations

from datetime import date as date_cls

from django.http import HttpRequest, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView

from apps.core.mixins import MetadataMixin

from .forms import BookingForm
from .services import BookingError, create_booking_from_payload, next_open_days, open_days_for_month


class BookingView(MetadataMixin, TemplateView):
    template_name = "pages/booking.html"
    meta_title = "Book a session"
    meta_description = (
        "Request a tattoo session: describe the idea, choose a style and placement, "
        "and upload reference images."
    )
    meta_robots = "noindex, follow"  # a form is not a landing page

    def get_context_data(self, **kwargs):
        from apps.core.models import SiteSettings

        ctx = super().get_context_data(**kwargs)
        ctx["page_name"] = "booking"
        ctx.setdefault("form", BookingForm())
        ctx["booking_open"] = SiteSettings.load().booking_open
        ctx["next_days"] = next_open_days(3)
        ctx["prefill_style"] = self.request.GET.get("style", "")
        ctx["availability_url"] = reverse("booking:availability_days")
        return ctx

    def post(self, request: HttpRequest, *args, **kwargs):
        from apps.core.models import SiteSettings

        if not SiteSettings.load().booking_open:
            ctx = self.get_context_data()
            ctx["booking_closed"] = True
            return render(request, self.template_name, ctx, status=403)

        form = BookingForm(request.POST, request.FILES)
        if not form.is_valid():
            ctx = self.get_context_data()
            ctx["form"] = form
            return render(request, self.template_name, ctx, status=400)

        data = form.cleaned_data
        payload = {
            "name": data["name"],
            "email": data["email"],
            "phone": data.get("phone", ""),
            "instagram": data.get("instagram", ""),
            "telegram": data.get("telegram", ""),
            "style": data.get("style"),
            "placement": data.get("placement", ""),
            "approx_size": data.get("approx_size", ""),
            "is_color": data.get("is_color"),
            "description": data.get("description", ""),
            "budget_min": data.get("budget_min"),
            "budget_max": data.get("budget_max"),
            "preferred_date": data.get("preferred_date"),
            "preferred_time": data.get("preferred_time", ""),
            "contact_consent": data.get("contact_consent", False),
            "source": "web",
        }

        files = request.FILES.getlist("references")
        try:
            booking = create_booking_from_payload(payload, files=files)
        except BookingError as exc:
            form.add_error(None, str(exc))
            ctx = self.get_context_data()
            ctx["form"] = form
            return render(request, self.template_name, ctx, status=400)

        from .services import notify_new_booking

        notify_new_booking(booking)

        return redirect(reverse("booking:success", kwargs={"reference": booking.reference}))


class BookingSuccessView(MetadataMixin, TemplateView):
    template_name = "pages/booking_success.html"
    meta_title = "Request received"
    meta_robots = "noindex, nofollow"  # confirmation pages must never be indexed

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_name"] = "booking_success"
        ctx["reference"] = self.kwargs.get("reference", "")
        return ctx


@require_GET
def availability_days(request: HttpRequest) -> JsonResponse:
    """
    JSON: which dates in a month are bookable.

    Powers the calendar widget. Returns an empty list rather than an error when
    availability has not been configured, so the widget degrades to a plain date input.
    """
    today = timezone.localdate()
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
        if not (1 <= month <= 12) or not (2000 <= year <= 2100):
            raise ValueError
    except (TypeError, ValueError):
        return JsonResponse({"error": "invalid year or month"}, status=400)

    days = open_days_for_month(year, month)
    return JsonResponse({
        "year": year,
        "month": month,
        "open_days": [d.isoformat() for d in days],
        "count": len(days),
    })


@require_GET
def availability_slots(request: HttpRequest) -> JsonResponse:
    """JSON: the slots for one date, with a state per slot."""
    raw = request.GET.get("date", "")
    try:
        day = date_cls.fromisoformat(raw)
    except (TypeError, ValueError):
        return JsonResponse({"error": "date must be ISO format (YYYY-MM-DD)"}, status=400)

    from .services import slots_for_day

    slots = slots_for_day(day)
    return JsonResponse({
        "date": day.isoformat(),
        "slots": [
            {
                "start": s.start.isoformat(),
                "end": s.end.isoformat(),
                "available": s.available,
                "reason": s.reason,
            }
            for s in slots
        ],
        "summary": {
            "available": sum(1 for s in slots if s.available),
            "total": len(slots),
        },
    })
