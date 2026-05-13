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
    """Модель вернула невалидный JSON или не по схеме."""

    default_message = "AI returned invalid response."
    default_code = "ai_invalid_response"
    status_code = 502


class AiNoValidPlaces(AiError):
    """Все place_id от модели — hallucinated, после фильтра ничего не осталось."""

    default_message = "AI did not return valid places."
    default_code = "ai_no_valid_places"
    status_code = 502