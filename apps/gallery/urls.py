"""Gallery URLs."""
from django.urls import path

from . import views

app_name = "gallery"

urlpatterns = [
    path("", views.GalleryView.as_view(), name="index"),
    path("<slug:slug>/", views.CollectionDetailView.as_view(), name="collection"),
]
