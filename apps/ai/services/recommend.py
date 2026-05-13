"""
Сервис рекомендаций "Куда пойти?".

Флоу:
1. Сборка контекста (с кэшем) + список валидных place_id.
2. Сборка user-сообщения (query + профиль пользователя).
3. Вызов LLMClient.complete() со structured output (Gemini JSON mode).
4. Парсинг JSON-ответа.
5. Фильтр hallucinated place_id по white list.
6. Лог запроса в AiRequestLog (всегда — и при ошибке тоже).
7. Возврат списка рекомендаций с обогащением (name из БД, чтобы не верить модели).
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any

from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth import get_user_model

from apps.ai.clients.base import LLMClient, LLMError, LLMMessage
from apps.ai.clients.factory import get_llm_client
from apps.ai.models import AiRequestLog, AiRequestStatus
from apps.ai.prompts import (
    RECOMMEND_RESPONSE_SCHEMA,
    SYSTEM_PROMPT_TEMPLATE,
    build_user_message,
)
from apps.ai.services.context import build_context
from apps.ai.services.cost import calc_cost_usd
from apps.ai.services.exceptions import (
    AiInvalidResponse,
    AiNoValidPlaces,
    AiProviderError,
)
from apps.places.models import Place

User = get_user_model()

# Не больше 3 рекомендаций — UX. Если модель выдала 10, режем здесь.
MAX_RECOMMENDATIONS = 3
# Сколько вообще принимаем от модели, до пост-фильтра.
LLM_MAX_RESPONSE_ITEMS = 5

# Подбираем под наш контекст: ~5K на system + ~200 на user = ~5.2K input;
# на ответ хватает 600-800 (3 места × ~150 токенов reasoning).
MAX_OUTPUT_TOKENS = 800


@dataclass(frozen=True)
class Recommendation:
    """Одна позиция в ответе /api/ai/recommend."""

    place_id: int
    name: str
    reasoning: str
    vibe_match: list[str]


@dataclass(frozen=True)
class RecommendResult:
    """Итог работы сервиса для view."""

    items: list[Recommendation]
    log_id: int


async def recommend(*, user_id: int, query: str) -> RecommendResult:
    """
    Главный entry-point. Возвращает рекомендации + id лога.

    Бросает AiProviderError / AiInvalidResponse / AiNoValidPlaces при ошибках.
    Лог пишется ВСЕГДА (включая ошибочные кейсы) — для дебага и контроля стоимости.
    """
    user = await _get_user(user_id)
    context = await sync_to_async(build_context)()
    system = SYSTEM_PROMPT_TEMPLATE.format(context=context.text)
    user_message = build_user_message(
        query=query,
        preferred_vibes=list(user.preferred_vibes or []),
        ai_context=user.ai_context or "",
    )

    client: LLMClient = get_llm_client()
    started_at = time.perf_counter()

    try:
        response = await client.complete(
            system=system,
            messages=[LLMMessage(role="user", content=user_message)],
            max_tokens=MAX_OUTPUT_TOKENS,
            temperature=0.7,
            response_schema=RECOMMEND_RESPONSE_SCHEMA,
        )
    except LLMError as exc:
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        await _log_error(
            user_id=user_id,
            query=query,
            model=getattr(exc, "provider", "unknown"),
            latency_ms=latency_ms,
            error=str(exc)[:500],
        )
        raise AiProviderError(str(exc)) from exc

    latency_ms = int((time.perf_counter() - started_at) * 1000)

    # Парсим JSON. Gemini в JSON-mode возвращает валидный JSON, но
    # на всякий случай ловим исключение — модель может вернуть пустой
    # текст при срабатывании safety filter.
    try:
        raw = json.loads(response.text)
        raw_items = raw.get("items", [])
        if not isinstance(raw_items, list):
            raise ValueError("items is not a list")
    except (json.JSONDecodeError, ValueError) as exc:
        await _log_error(
            user_id=user_id,
            query=query,
            model=response.model,
            latency_ms=latency_ms,
            error=f"invalid_json: {exc}"[:500],
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cached_input_tokens=response.cached_input_tokens,
        )
        raise AiInvalidResponse(f"invalid JSON from model: {exc}") from exc

    # Фильтрация и валидация
    items = _filter_and_enrich(
        raw_items=raw_items[:LLM_MAX_RESPONSE_ITEMS],
        valid_ids=context.valid_place_ids,
    )

    if not items:
        await _log_error(
            user_id=user_id,
            query=query,
            model=response.model,
            latency_ms=latency_ms,
            error="no_valid_places_after_filter",
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cached_input_tokens=response.cached_input_tokens,
        )
        raise AiNoValidPlaces("AI returned no valid places after filtering.")

    items = items[:MAX_RECOMMENDATIONS]

    # Обогащаем name из БД — не доверяем модели name'у, даже если в схеме
    place_ids = [item["place_id"] for item in items]
    names_by_id = await _get_place_names(place_ids)

    recommendations = [
        Recommendation(
            place_id=item["place_id"],
            name=names_by_id.get(item["place_id"], ""),
            reasoning=item["reasoning"],
            vibe_match=item["vibe_match"],
        )
        for item in items
    ]

    log = await _log_success(
        user_id=user_id,
        query=query,
        recommendations=recommendations,
        model=response.model,
        latency_ms=latency_ms,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cached_input_tokens=response.cached_input_tokens,
    )

    return RecommendResult(items=recommendations, log_id=log.pk)


def _filter_and_enrich(
    *, raw_items: list[Any], valid_ids: frozenset[int]
) -> list[dict[str, Any]]:
    """
    Фильтрует hallucinated id и нормализует поля.
    Дубликаты place_id убираем (первое вхождение остаётся).
    """
    result: list[dict[str, Any]] = []
    seen: set[int] = set()
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        pid = raw.get("place_id")
        if not isinstance(pid, int) or pid not in valid_ids or pid in seen:
            continue
        reasoning = raw.get("reasoning", "")
        if not isinstance(reasoning, str) or not reasoning.strip():
            continue
        vibe_match_raw = raw.get("vibe_match") or []
        if not isinstance(vibe_match_raw, list):
            vibe_match_raw = []
        vibe_match = [v for v in vibe_match_raw if isinstance(v, str)][:3]

        seen.add(pid)
        result.append(
            {
                "place_id": pid,
                "reasoning": reasoning.strip()[:500],
                "vibe_match": vibe_match,
            }
        )
    return result


# ---- async DB helpers --------------------------------------------------

@sync_to_async
def _get_user(user_id: int):  # type: ignore[no-untyped-def]
    return User.objects.only("id", "preferred_vibes", "ai_context").get(pk=user_id)


@sync_to_async
def _get_place_names(ids: list[int]) -> dict[int, str]:
    return dict(Place.objects.filter(pk__in=ids).values_list("id", "name"))


@sync_to_async
def _log_success(
    *,
    user_id: int,
    query: str,
    recommendations: list[Recommendation],
    model: str,
    latency_ms: int,
    input_tokens: int,
    output_tokens: int,
    cached_input_tokens: int,
) -> AiRequestLog:
    return AiRequestLog.objects.create(
        user_id=user_id,
        query=query[:500],
        response_summary=[
            {"place_id": r.place_id, "reasoning": r.reasoning[:120]}
            for r in recommendations
        ],
        model=model,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=cached_input_tokens,
        cost_usd=calc_cost_usd(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_input_tokens,
        ),
        status=AiRequestStatus.OK,
    )


@sync_to_async
def _log_error(
    *,
    user_id: int,
    query: str,
    model: str,
    latency_ms: int,
    error: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cached_input_tokens: int = 0,
) -> AiRequestLog:
    return AiRequestLog.objects.create(
        user_id=user_id,
        query=query[:500],
        response_summary=[],
        model=model,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=cached_input_tokens,
        cost_usd=calc_cost_usd(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_input_tokens,
        ),
        status=AiRequestStatus.ERROR,
        error=error,
    )