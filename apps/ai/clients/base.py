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
    """Любая ошибка LLM-провайдера. Сервис ловит и решает что показать юзеру."""

    def __init__(
        self, message: str, *, provider: str, status_code: int | None = None
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code