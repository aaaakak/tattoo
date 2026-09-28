"""Shop URLs."""
from django.urls import path

from . import views

app_name = "shop"

urlpatterns = [
    path("", views.ProductListView.as_view(), name="list"),
    path("<slug:slug>/", views.ProductDetailView.as_view(), name="detail"),
]
