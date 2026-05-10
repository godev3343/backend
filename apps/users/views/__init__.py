"""Реэкспорт view-классов для удобства импорта в urls.py."""
from apps.users.views.email_verify import (
    EmailVerifyConfirmView,
    EmailVerifyRequestView,
)
from apps.users.views.google import GoogleAuthView
from apps.users.views.onboarding import OnboardingView
from apps.users.views.password_reset import (
    PasswordResetConfirmView,
    PasswordResetRequestView,
)
from apps.users.views.register import LoginView, RegisterView
from apps.users.views.tokens import LogoutView, TokenRefreshView

__all__ = [
    "EmailVerifyConfirmView",
    "EmailVerifyRequestView",
    "GoogleAuthView",
    "LoginView",
    "LogoutView",
    "OnboardingView",
    "PasswordResetConfirmView",
    "PasswordResetRequestView",
    "RegisterView",
    "TokenRefreshView",
]