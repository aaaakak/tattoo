"""Tattoo portfolio URLs. Views arrive in Phase 6."""
from django.urls import path

from . import views

app_name = "tattoos"

urlpatterns = [
    path("", views.TattooListView.as_view(), name="list"),
    path("<slug:slug>/", views.TattooDetailView.as_view(), name="detail"),
]
