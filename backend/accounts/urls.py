from __future__ import annotations

from django.urls import path

from .views import CurrentUserView, SessionLoginView, SessionLogoutView, SessionRegisterView

urlpatterns = [
    path("auth/register/", SessionRegisterView.as_view(), name="auth-register"),
    path("auth/login/", SessionLoginView.as_view(), name="auth-login"),
    path("auth/logout/", SessionLogoutView.as_view(), name="auth-logout"),
    path("auth/me/", CurrentUserView.as_view(), name="auth-me"),
]
