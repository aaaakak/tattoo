"""Artist / about URLs."""
from django.urls import path

from . import views

app_name = "artists"

urlpatterns = [
    path("", views.AboutView.as_view(), name="about"),
]
