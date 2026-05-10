"""Единый формат ошибок API."""
from __future__ import annotations

import structlog
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from apps.core.exceptions import DomainError

logger = structlog.get_logger(__name__)


def api_exception_handler(exc: Exception, context: dict) -> Response | None:
    """
    Конвертирует исключения в ответ вида:
      {"detail": "...", "code": "...", "errors": {...}}
    """
    # Доменные ошибки конвертируем в DRF-исключения с кодом
    if isinstance(exc, DomainError):
        payload: dict = {"detail": exc.message, "code": exc.code}
        if exc.errors is not None:
            payload["errors"] = exc.errors
        return Response(payload, status=exc.status_code)

    response = exception_handler(exc, context)

    if response is None:
        # Не-DRF исключение — лог + 500
        request = context.get("request")
        user_id = getattr(getattr(request, "user", None), "id", None)
        logger.exception("unhandled_api_error", user_id=user_id)
        return Response(
            {"detail": "Internal server error", "code": "internal_error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Унифицируем формат
    data = response.data
    code = "error"
    detail: str | dict = data
    errors: dict | None = None

    if isinstance(data, dict):
        if "detail" in data:
            detail = data["detail"]
            code = getattr(data["detail"], "code", code)
        else:
            detail = "Validation error"
            code = "validation_error"
            errors = data
    elif isinstance(data, list):
        detail = "; ".join(str(x) for x in data)

    response.data = {"detail": str(detail), "code": code}
    if errors is not None:
        response.data["errors"] = errors

    return response