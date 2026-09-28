"""Booking URLs."""

from django.urls import path

from . import views

app_name = "booking"

urlpatterns = [
    path("", views.BookingView.as_view(), name="create"),
    path("success/<str:reference>/", views.BookingSuccessView.as_view(), name="success"),
    path("api/availability/days/", views.availability_days, name="availability_days"),
    path("api/availability/slots/", views.availability_slots, name="availability_slots"),
]
