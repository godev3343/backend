"""Базовые доменные исключения. Бросаются из services/, ловятся handler-ом."""
from __future__ import annotations

from rest_framework import status


class DomainError(Exception):
    """Базовый класс для бизнес-ошибок."""

    code: str = "domain_error"
    status_code: int = status.HTTP_400_BAD_REQUEST
    message: str = "Domain error"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        errors: dict | None = None,
    ) -> None:
        self.message = message or self.message
        if code:
            self.code = code
        self.errors = errors
        super().__init__(self.message)


class NotFoundError(DomainError):
    code = "not_found"
    status_code = status.HTTP_404_NOT_FOUND
    message = "Resource not found"


class ConflictError(DomainError):
    code = "conflict"
    status_code = status.HTTP_409_CONFLICT
    message = "Conflict"


class PermissionError_(DomainError):
    code = "forbidden"
    status_code = status.HTTP_403_FORBIDDEN
    message = "Forbidden"


class ValidationError_(DomainError):
    code = "validation_error"
    status_code = status.HTTP_400_BAD_REQUEST
    message = "Validation error"