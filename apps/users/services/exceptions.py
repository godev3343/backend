"""Ошибки auth-домена. Наследуются от DomainError (НЕ от APIException)."""
from __future__ import annotations

from apps.core.exceptions import DomainError


class AuthError(DomainError):
    """База для всех auth-ошибок."""

    default_message = "Authentication error."
    default_code = "auth_error"
    status_code = 400


class InvalidCredentials(AuthError):
    default_message = "Invalid credentials."
    default_code = "invalid_credentials"
    status_code = 401


class EmailAlreadyExists(AuthError):
    default_message = "Email is already registered."
    default_code = "email_exists"
    status_code = 409


class InvalidCode(AuthError):
    default_message = "Code is invalid or expired."
    default_code = "invalid_code"
    status_code = 400


class InvalidResetToken(AuthError):
    default_message = "Reset token is invalid or expired."
    default_code = "invalid_reset_token"
    status_code = 400


class UserNotFound(AuthError):
    default_message = "User not found."
    default_code = "user_not_found"
    status_code = 404


# ---------- Google ---------------------------------------------------------


class GoogleAuthError(AuthError):
    default_message = "Google authentication failed."
    default_code = "google_auth_failed"
    status_code = 400