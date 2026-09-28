"""Artist authentication URLs."""
from django.contrib.auth import views as auth_views
from django.urls import path

app_name = "accounts"

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="pages/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="core:home"), name="logout"),
    path(
        "password/",
        auth_views.PasswordChangeView.as_view(
            template_name="pages/password_change.html",
            success_url="/admin/",
        ),
        name="password_change",
    ),
]
