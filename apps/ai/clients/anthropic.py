"""Anthropic-реализация — заглушка, подключим позже."""
from __future__ import annotations

from apps.ai.clients.base import LLMClient, LLMError, LLMMessage, LLMResponse


class AnthropicClient(LLMClient):
    def __init__(self, api_key: str, model: str = "claude-haiku-4-5") -> None:
        # TODO: реальная реализация на anthropic SDK с prompt caching
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY is empty", provider="anthropic")
        self._api_key = api_key
        self._model = model

    async def complete(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> LLMResponse:
        raise NotImplementedError("Anthropic client is not wired yet — use AI_PROVIDER=gemini")