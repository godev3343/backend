"""
Базовые исключения для всех доменных сервисов проекта.

DomainError — НЕ DRF APIException. Это чистый Python Exception с
атрибутами message/code/status_code/errors, который перехватывается
в apps/core/exception_handler.api_exception_handler и конвертируется
в единообразный JSON-ответ.

Каждое приложение наследует свой <Domain>Error от DomainError и
определяет конкретные ошибки от него.
"""
from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """
    Базовый класс для всех доменных ошибок.

    Не использовать напрямую — наследовать AuthError, FriendshipError и т.д.
    Наследники переопределяют default_message / default_code / status_code.
    """

    default_message: str = "Service error."
    default_code: str = "service_error"
    status_code: int = 400

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        errors: dict[str, Any] | None = None,
        status_code: int | None = None,
    ) -> None:
        self.message: str = message or self.default_message
        self.code: str = code or self.default_code
        self.errors: dict[str, Any] | None = errors
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.message)


# Алиас для обратной совместимости с моим прошлым артефактом — не использовать в новом коде.
ServiceError = DomainError