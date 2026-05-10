"""Auth и onboarding endpoints."""
from __future__ import annotations

from django.urls import path

from apps.users.views import (
    EmailVerifyConfirmView,
    EmailVerifyRequestView,
    GoogleAuthView,
    LoginView,
    LogoutView,
    OnboardingView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegisterView,
    TokenRefreshView,
)

app_name = "users"

urlpatterns = [
    # Auth
    path("auth/register", RegisterView.as_view(), name="register"),
    path("auth/login", LoginView.as_view(), name="login"),
    path("auth/refresh", TokenRefreshView.as_view(), name="refresh"),
    path("auth/logout", LogoutView.as_view(), name="logout"),
    # Email verification
    path(
        "auth/email/verify/request",
        EmailVerifyRequestView.as_view(),
        name="email_verify_request",
    ),
    path(
        "auth/email/verify/confirm",
        EmailVerifyConfirmView.as_view(),
        name="email_verify_confirm",
    ),
    # Password reset
    path(
        "auth/password/reset/request",
        PasswordResetRequestView.as_view(),
        name="password_reset_request",
    ),
    path(
        "auth/password/reset/confirm",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    # Google OAuth
    path("auth/google", GoogleAuthView.as_view(), name="google_auth"),
    # Onboarding
    path("users/me/onboarding", OnboardingView.as_view(), name="onboarding"),
]