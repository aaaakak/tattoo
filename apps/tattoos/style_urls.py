"""Tattoo style index URLs."""
from django.urls import path

from . import views

app_name = "styles"

urlpatterns = [
    path("", views.StyleListView.as_view(), name="index"),
    path("<slug:slug>/", views.StyleDetailView.as_view(), name="detail"),
]
