"""Gemini-реализация LLMClient через google-genai SDK."""

from __future__ import annotations

import asyncio
from typing import Any

from google import genai
from google.genai import types

from apps.ai.clients.base import LLMClient, LLMError, LLMMessage, LLMResponse


class GeminiClient(LLMClient):
    """
    Использует google-genai SDK.

    Бесплатный тариф через AI Studio — задаём ключ через GEMINI_API_KEY.
    Модели: 'gemini-2.5-flash' (быстро, дёшево) — аналог Haiku.
            'gemini-2.5-pro'   (умнее) — аналог Sonnet.

    Structured output: если передан response_schema, выставляем
    response_mime_type='application/json' и response_schema — модель
    возвращает строго JSON по схеме. Это нативная фича Gemini, надёжнее
    текстового парсинга.
    """

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        if not api_key:
            raise LLMError("GEMINI_API_KEY is empty", provider="gemini")
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def complete(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        max_tokens: int = 1024,
        temperature: float = 0.7,
        response_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:
        try:
            contents = self._to_gemini_contents(messages)
            config_kwargs: dict[str, Any] = {
                "system_instruction": system or None,
                "max_output_tokens": max_tokens,
                "temperature": temperature,
            }
            if response_schema is not None:
                # Gemini JSON mode — модель возвращает строго по схеме.
                # SDK принимает dict-схему в формате OpenAPI subset.
                config_kwargs["response_mime_type"] = "application/json"
                config_kwargs["response_schema"] = response_schema

            config = types.GenerateContentConfig(**config_kwargs)
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=contents,
                config=config,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # SDK бросает разные типы — нормализуем
            raise LLMError(str(exc), provider="gemini") from exc

        text = response.text or ""
        usage = response.usage_metadata

        return LLMResponse(
            text=text,
            input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
            output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
            cached_input_tokens=getattr(usage, "cached_content_token_count", 0) or 0,
            model=self._model,
        )

    @staticmethod
    def _to_gemini_contents(messages: list[LLMMessage]) -> list[types.Content]:
        """Конвертирует унифицированный формат в Gemini Content."""
        result: list[types.Content] = []
        for msg in messages:
            # Gemini использует role "user" и "model" (не "assistant")
            role = "model" if msg.role == "assistant" else "user"
            result.append(types.Content(role=role, parts=[types.Part.from_text(text=msg.content)]))
        return result
