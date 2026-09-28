"""Artwork portfolio URLs."""
from django.urls import path

from . import views

app_name = "artworks"

urlpatterns = [
    path("", views.ArtworkListView.as_view(), name="list"),
    path("category/<slug:slug>/", views.CategoryDetailView.as_view(), name="category"),
    path("<slug:slug>/", views.ArtworkDetailView.as_view(), name="detail"),
]
