"""Возвращает LLMClient по env-конфигу."""

from __future__ import annotations

from functools import lru_cache

from django.conf import settings

from apps.ai.clients.anthropic import AnthropicClient
from apps.ai.clients.base import LLMClient, LLMError
from apps.ai.clients.gemini import GeminiClient


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    """
    Singleton по процессу. На asyncio-воркере один клиент = один HTTPX pool.
    Кэш сбросится при перезапуске — этого достаточно.
    """
    provider = settings.AI_PROVIDER.lower()

    if provider == "gemini":
        return GeminiClient(
            api_key=settings.GEMINI_API_KEY,
            model=getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash"),
        )

    if provider == "anthropic":
        return AnthropicClient(
            api_key=settings.ANTHROPIC_API_KEY,
            model=getattr(settings, "ANTHROPIC_MODEL", "claude-haiku-4-5"),
        )

    raise LLMError(f"Unknown AI_PROVIDER: {provider}", provider=provider)
