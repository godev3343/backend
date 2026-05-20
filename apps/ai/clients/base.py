"""Абстрактный LLM-клиент. Реализации — Anthropic, Gemini и т.д."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class LLMMessage:
    """Универсальное сообщение для LLM."""

    role: str  # "user" | "assistant" | "system"
    content: str


@dataclass(frozen=True)
class LLMResponse:
    """Ответ модели."""

    text: str
    input_tokens: int
    output_tokens: int
    model: str
    # Для кэширования (Anthropic) или контекстного кэша (Gemini) — расширим позже
    cached_input_tokens: int = 0


class LLMClient(Protocol):
    """
    Минимальный контракт LLM-клиента.

    Реализации:
      - apps/ai/clients/gemini.py
      - apps/ai/clients/anthropic.py (позже)

    response_schema: JSON-схема для structured output. Если задана,
    клиент инструктирует модель отвечать строго в JSON по этой схеме.
    Текст ответа в LLMResponse.text — валидный JSON.
    Без response_schema — свободный текст.

    Если ответ модели нельзя вернуть как LLMResponse (пустой текст,
    safety-блок, MAX_TOKENS truncate, rate limit) — клиент бросает
    конкретный наследник LLMError. Сервис различает типы ошибок
    и решает retry/fallback.
    """

    async def complete(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        max_tokens: int = 1024,
        temperature: float = 0.7,
        response_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Сгенерировать ответ. Бросает LLMError при ошибке."""
        ...


class LLMError(Exception):
    """
    Базовая ошибка LLM-провайдера.

    Наследники различают причины — это нужно сервису, чтобы решить:
    — retry'ить или нет,
    — мапить в какой HTTP-ответ юзеру,
    — что писать в AiRequestLog.error.

    Дефолт `retryable=False` — большинство ошибок не имеет смысла повторять
    (auth, blocked, неконфигурированный API key). Транзиентные подклассы
    переопределяют это в True.
    """

    retryable: bool = False

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code


class LLMRateLimited(LLMError):
    """
    429 / RESOURCE_EXHAUSTED от провайдера. На free tier Gemini это
    основной кейс. Retry внутри одного запроса бесполезен — лимит per-минута/день.
    Пусть юзер повторит позже. Сервис превращает в AiRateLimited (503 + Retry-After).
    """

    retryable = False

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message, provider=provider, status_code=429)
        self.retry_after_seconds = retry_after_seconds


class LLMBlocked(LLMError):
    """
    Safety filter заблокировал prompt или response. Retry с теми же входами
    не разблокирует — модель будет блокировать стабильно. Сервис мапит
    в AiBlockedByModeration (422).
    """

    retryable = False


class LLMTruncated(LLMError):
    """
    Модель упёрлась в max_output_tokens (finish_reason=MAX_TOKENS).
    На gemini-2.5-flash это часто значит, что thinking-токены съели бюджет
    и text=''. Retry имеет смысл — на повторе модель может уложиться.
    """

    retryable = True


class LLMEmpty(LLMError):
    """
    Модель вернула непустой кандидат, но text=''. Случается при
    finish_reason=OTHER, RECITATION, или просто странных входах.
    Retry с пониженной температурой имеет шанс помочь.
    """

    retryable = True