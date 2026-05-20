"""AI-домен ошибки. Наследуются от DomainError, не от APIException."""

from __future__ import annotations

from apps.core.exceptions import DomainError


class AiError(DomainError):
    default_message = "AI service error."
    default_code = "ai_error"
    status_code = 500


class AiProviderError(AiError):
    """Ошибка LLM-провайдера (timeout, 5xx от API)."""

    default_message = "AI provider unavailable."
    default_code = "ai_provider_error"
    status_code = 502


class AiInvalidResponse(AiError):
    """
    Модель вернула невалидный JSON или не по схеме после всех retry.
    Это означает что модель устойчиво не может уложиться в формат —
    обычно UX-проблема, не транзиентная.
    """

    default_message = "AI returned invalid response."
    default_code = "ai_invalid_response"
    status_code = 502


class AiNoValidPlaces(AiError):
    """Все place_id от модели — hallucinated, после фильтра ничего не осталось."""

    default_message = "AI did not return valid places."
    default_code = "ai_no_valid_places"
    status_code = 502


class AiRateLimited(AiError):
    """
    Провайдер вернул 429. На free tier Gemini это обычное дело
    (10 RPM / ~250 RPD). Возвращаем 503 + Retry-After хедер
    через view, фронт показывает «попробуйте через минуту».
    """

    default_message = "AI is temporarily rate-limited. Try again shortly."
    default_code = "ai_rate_limited"
    status_code = 503

    def __init__(
        self,
        message: str | None = None,
        *,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class AiBlockedByModeration(AiError):
    """
    Safety-фильтр модели заблокировал prompt или response. Запрос
    обрабатывается корректно (это не баг бэка), но юзеру надо
    переформулировать. 422 = Unprocessable Entity по семантике.
    """

    default_message = "AI could not process this query due to content policy."
    default_code = "ai_blocked"
    status_code = 422