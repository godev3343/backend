"""Gemini-реализация LLMClient через google-genai SDK."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from google import genai
from google.genai import types

from apps.ai.clients.base import (
    LLMBlocked,
    LLMClient,
    LLMEmpty,
    LLMError,
    LLMMessage,
    LLMRateLimited,
    LLMResponse,
    LLMTruncated,
)

logger = logging.getLogger(__name__)

# Модели, поддерживающие отключение thinking через thinking_budget=0.
# На gemini-2.5-pro минимум 128, отключить нельзя. На 2.0-flash параметра нет.
# Используем substring-проверку, чтобы покрывать preview-варианты типа
# "gemini-2.5-flash-preview-XX-YY".
_THINKING_DISABLEABLE_PREFIXES = ("gemini-2.5-flash", "gemini-3-flash")


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

    Thinking-модели (2.5+): на flash принудительно отключаем thinking
    (thinking_budget=0). Иначе thinking-токены съедают max_output_tokens
    и при structured output модель возвращает text='' с
    finish_reason=MAX_TOKENS. См. googleapis/python-genai#782.
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
        config = self._build_config(
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            response_schema=response_schema,
        )
        contents = self._to_gemini_contents(messages)

        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=contents,
                config=config,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # SDK бросает разные типы — нормализуем
            self._raise_from_sdk_exception(exc)

        return self._build_llm_response(response)

    # ---- response handling ---------------------------------------------

    def _build_llm_response(self, response: Any) -> LLMResponse:
        """
        Превращает SDK-response в LLMResponse или бросает конкретный LLMError.

        Порядок проверок:
        1. prompt_feedback.block_reason — prompt отвергнут до генерации.
        2. Нет кандидатов — странный кейс, но возможен.
        3. finish_reason: SAFETY/RECITATION/BLOCKLIST/SPII → LLMBlocked.
                         MAX_TOKENS → LLMTruncated.
                         STOP/None → ожидаемо, продолжаем.
        4. text пустой при STOP → LLMEmpty.
        """
        usage = getattr(response, "usage_metadata", None)
        input_tokens = self._safe_int(getattr(usage, "prompt_token_count", 0))
        output_tokens = self._safe_int(getattr(usage, "candidates_token_count", 0))
        cached_input_tokens = self._safe_int(getattr(usage, "cached_content_token_count", 0))

        # 1. Prompt заблокирован — модель ничего не сгенерировала.
        prompt_feedback = getattr(response, "prompt_feedback", None)
        block_reason = getattr(prompt_feedback, "block_reason", None)
        if block_reason:
            raise LLMBlocked(
                f"prompt_blocked: {self._enum_name(block_reason)}",
                provider="gemini",
            )

        # 2. Кандидатов нет вообще.
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            logger.warning(
                "gemini returned no candidates and no block_reason; usage=%s",
                usage,
            )
            raise LLMEmpty("no candidates in response", provider="gemini")

        candidate = candidates[0]
        finish_reason_name = self._enum_name(getattr(candidate, "finish_reason", None))

        # 3. Разбор finish_reason.
        if finish_reason_name in {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"}:
            raise LLMBlocked(
                f"candidate_blocked: {finish_reason_name}",
                provider="gemini",
            )

        # 4. Текст ответа. SDK property .text иногда бросает ValueError на
        # пустом candidate, поэтому собираем из parts вручную.
        text = self._extract_text(candidate) or ""

        if finish_reason_name == "MAX_TOKENS":
            # Лог пишем — это самый частый кейс с thinking-моделями.
            logger.warning(
                "gemini truncated by MAX_TOKENS; text_len=%d input=%d output=%d cached=%d",
                len(text),
                input_tokens,
                output_tokens,
                cached_input_tokens,
            )
            raise LLMTruncated(
                f"max_tokens_reached: text_len={len(text)}",
                provider="gemini",
            )

        if not text.strip():
            logger.warning(
                "gemini returned empty text; finish_reason=%s usage=%s",
                finish_reason_name,
                usage,
            )
            raise LLMEmpty(
                f"empty_text: finish_reason={finish_reason_name or 'unknown'}",
                provider="gemini",
            )

        return LLMResponse(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_input_tokens,
            model=self._model,
        )

    # ---- config build --------------------------------------------------

    def _build_config(
        self,
        *,
        system: str,
        max_tokens: int,
        temperature: float,
        response_schema: dict[str, Any] | None,
    ) -> types.GenerateContentConfig:
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

        # Отключаем thinking на flash — иначе thinking-токены сжирают
        # max_output_tokens и при structured output text приходит пустым.
        # На pro/non-2.5 моделях параметр не передаём (SDK ругается).
        if self._supports_disabling_thinking():
            config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)

        return types.GenerateContentConfig(**config_kwargs)

    def _supports_disabling_thinking(self) -> bool:
        return self._model.startswith(_THINKING_DISABLEABLE_PREFIXES)

    # ---- exception mapping ---------------------------------------------

    def _raise_from_sdk_exception(self, exc: Exception) -> None:
        """
        google-genai бросает разные типы исключений на разные HTTP-коды.
        Мапим их в наши LLMError-подклассы. Если не распознали — общий LLMError.
        """
        message = str(exc)
        status_code = self._extract_status_code(exc, message)

        if status_code == 429 or "RESOURCE_EXHAUSTED" in message:
            retry_after = self._extract_retry_after(message)
            raise LLMRateLimited(
                message[:500],
                provider="gemini",
                retry_after_seconds=retry_after,
            ) from exc

        raise LLMError(message[:500], provider="gemini", status_code=status_code) from exc

    @staticmethod
    def _extract_status_code(exc: Exception, message: str) -> int | None:
        """SDK-исключения имеют разные атрибуты под код. Пробуем по очереди."""
        for attr in ("code", "status_code"):
            value = getattr(exc, attr, None)
            if isinstance(value, int):
                return value
        # Фолбэк — парсим первые 3 цифры из текста (e.g. "429 Resource exhausted").
        match = re.search(r"\b(\d{3})\b", message)
        if match:
            return int(match.group(1))
        return None

    @staticmethod
    def _extract_retry_after(message: str) -> int | None:
        """
        Quota-ответы Gemini содержат поле retry_delay {seconds: N} в JSON
        тела ошибки. Парсим осторожно — формат может меняться.
        """
        match = re.search(r"retry[_-]?delay.*?seconds[\":\s]*(\d+)", message, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

    # ---- low-level helpers ---------------------------------------------

    @staticmethod
    def _to_gemini_contents(messages: list[LLMMessage]) -> list[types.Content]:
        """Конвертирует унифицированный формат в Gemini Content."""
        contents: list[types.Content] = []
        for msg in messages:
            # Gemini не знает "system" в content — system_instruction отдельно.
            # Если кто-то прислал system здесь, считаем за user.
            role = "user" if msg.role in ("user", "system") else "model"
            contents.append(
                types.Content(role=role, parts=[types.Part.from_text(text=msg.content)])
            )
        return contents

    @staticmethod
    def _extract_text(candidate: Any) -> str:
        """Собирает текст из candidate.content.parts, безопасно к пустоте."""
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        chunks: list[str] = []
        for part in parts:
            # thought-парты пропускаем — это служебные мысли модели.
            if getattr(part, "thought", False):
                continue
            text = getattr(part, "text", None)
            if isinstance(text, str):
                chunks.append(text)
        return "".join(chunks)

    @staticmethod
    def _enum_name(value: Any) -> str | None:
        """SDK иногда отдаёт enum (с .name), иногда строку. Нормализуем в str."""
        if value is None:
            return None
        name = getattr(value, "name", None)
        if isinstance(name, str):
            return name
        return str(value)

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0