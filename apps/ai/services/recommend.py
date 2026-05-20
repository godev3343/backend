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

Retry-логика:
- Один retry с пониженной температурой на транзиентные ошибки
  (LLMTruncated, LLMEmpty, JSONDecodeError). На gemini-2.5-flash thinking
  иногда сжирает max_output_tokens — повтор без thinking-budget'а часто
  спасает. Подробности — apps/ai/clients/gemini.py.
- НЕ retry'им: LLMRateLimited (бесполезно — лимит per-минута/день),
  LLMBlocked (safety filter будет блокировать повторно).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model

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
    AiBlockedByModeration,
    AiInvalidResponse,
    AiNoValidPlaces,
    AiProviderError,
    AiRateLimited,
)
from apps.places.models import Place

logger = logging.getLogger(__name__)

User = get_user_model()

# Не больше 3 рекомендаций — UX. Если модель выдала 10, режем здесь.
MAX_RECOMMENDATIONS = 3
# Сколько вообще принимаем от модели, до пост-фильтра.
LLM_MAX_RESPONSE_ITEMS = 5

# 2000 вместо прежних 800: на gemini-2.5-flash thinking-токены учитываются
# в max_output_tokens. Даже с thinking_budget=0 (см. gemini.py) на сложных
# структурных ответах модель может «забыть» отключить thinking — это
# известный bug в SDK (googleapis/python-genai#782). Поднимаем потолок,
# чтобы оставить запас. Стоимость на flash: $2.50/1M output × ~800 токенов
# на полный ответ ≈ $0.002. Лишний потолок — не лишние списания.
MAX_OUTPUT_TOKENS = 2000

# Температура на основной попытке и на retry. Понижаем на повторе —
# детерминизм увеличивает шанс что модель уложится в формат и токены.
PRIMARY_TEMPERATURE = 0.7
RETRY_TEMPERATURE = 0.2

# Когда не знаем имени модели (LLMError до получения response) — пишем
# что использовали по конфигу. Это лучше, чем хардкод "unknown" —
# для аналитики стоимости/частоты ошибок по моделям полезно.
_UNKNOWN_MODEL = "unknown"


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

    Бросает AiProviderError / AiInvalidResponse / AiNoValidPlaces /
            AiRateLimited / AiBlockedByModeration при ошибках.
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

    # Внутри _call_with_retry либо вернётся валидный response + parsed items
    # с залогированными transient attempt'ами (для observability), либо
    # будет проброшено AiError-подкласс ПОСЛЕ записи в AiRequestLog.
    # То есть на выходе сюда — всегда успех.
    response, raw_items, attempt_errors = await _call_with_retry(
        client=client,
        system=system,
        user_message=user_message,
        user_id=user_id,
        query=query,
        started_at=started_at,
    )

    latency_ms = _elapsed_ms(started_at)

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
            error=_join_errors("no_valid_places_after_filter", attempt_errors),
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

    # Все ошибки на пути к успеху были транзиентными — но если их видели,
    # это сигнал для мониторинга промптов / лимитов.
    if attempt_errors:
        logger.info(
            "recommend succeeded after transient errors: user_id=%s attempts=%s",
            user_id,
            attempt_errors,
        )

    return RecommendResult(items=recommendations, log_id=log.pk)


# ---- retry loop ---------------------------------------------------------


async def _call_with_retry(
    *,
    client: LLMClient,
    system: str,
    user_message: str,
    user_id: int,
    query: str,
    started_at: float,
) -> tuple[LLMResponse, list[Any], list[str]]:
    """
    Делает основной вызов и при транзиентной ошибке — один retry.

    Возвращает (response, raw_items, attempt_errors), где attempt_errors —
    список причин неудач для observability (записываются в AiRequestLog
    при финальном успехе как метаданные, но через logger.info).

    На терминальной ошибке (после retry или сразу):
      1. Пишет AiRequestLog со status=ERROR через _log_error.
      2. Бросает соответствующий AiError-подкласс.

    Сервис снаружи не должен ловить AiError из этой функции — пробрасывает
    в view, где DRF api_exception_handler конвертит в HTTP-ответ.
    """
    attempt_errors: list[str] = []

    for attempt in range(2):
        temperature = PRIMARY_TEMPERATURE if attempt == 0 else RETRY_TEMPERATURE
        try:
            response = await client.complete(
                system=system,
                messages=[LLMMessage(role="user", content=user_message)],
                max_tokens=MAX_OUTPUT_TOKENS,
                temperature=temperature,
                response_schema=RECOMMEND_RESPONSE_SCHEMA,
            )
        except LLMRateLimited as exc:
            # 429 — терминально, retry бесполезен.
            await _log_error(
                user_id=user_id,
                query=query,
                model=_UNKNOWN_MODEL,
                latency_ms=_elapsed_ms(started_at),
                error=f"rate_limited: {exc}"[:500],
            )
            raise AiRateLimited(
                str(exc),
                retry_after_seconds=exc.retry_after_seconds,
            ) from exc
        except LLMBlocked as exc:
            # Safety — терминально, retry заблокируется так же.
            await _log_error(
                user_id=user_id,
                query=query,
                model=_UNKNOWN_MODEL,
                latency_ms=_elapsed_ms(started_at),
                error=f"blocked: {exc}"[:500],
            )
            raise AiBlockedByModeration(str(exc)) from exc
        except (LLMTruncated, LLMEmpty) as exc:
            attempt_errors.append(f"attempt_{attempt}:{type(exc).__name__}:{exc}")
            if attempt == 0:
                logger.info("retrying after transient LLM error: %s", exc)
                continue
            # Второй раз тоже не получилось — терминально.
            await _log_error(
                user_id=user_id,
                query=query,
                model=_UNKNOWN_MODEL,
                latency_ms=_elapsed_ms(started_at),
                error=_join_errors("retry_failed", attempt_errors),
            )
            raise AiInvalidResponse(str(exc)) from exc
        except LLMError as exc:
            # Неизвестная провайдерская ошибка (timeout, 5xx без распознанного
            # подтипа). Терминально — не понимаем причину, рисковать с retry
            # неразумно.
            await _log_error(
                user_id=user_id,
                query=query,
                model=_UNKNOWN_MODEL,
                latency_ms=_elapsed_ms(started_at),
                error=f"provider_error: {exc}"[:500],
            )
            raise AiProviderError(str(exc)) from exc

        # Получили response — парсим JSON.
        try:
            raw = json.loads(response.text)
            raw_items = raw.get("items", [])
            if not isinstance(raw_items, list):
                raise ValueError("items is not a list")
        except (json.JSONDecodeError, ValueError) as exc:
            attempt_errors.append(f"attempt_{attempt}:invalid_json:{exc}")
            if attempt == 0:
                logger.info("retrying after JSON parse error: %s", exc)
                continue
            # JSON всё ещё кривой — терминально.
            await _log_error(
                user_id=user_id,
                query=query,
                model=response.model,
                latency_ms=_elapsed_ms(started_at),
                error=_join_errors("invalid_json_after_retry", attempt_errors),
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cached_input_tokens=response.cached_input_tokens,
            )
            raise AiInvalidResponse(f"invalid JSON from model: {exc}") from exc

        # Дошли сюда — всё ок.
        return response, raw_items, attempt_errors

    # Невозможно по логике цикла, но mypy/линтер успокаиваются.
    raise AiInvalidResponse("retry loop exhausted unexpectedly")


def _elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def _join_errors(prefix: str, errors: list[str]) -> str:
    """Склеивает список ошибок в одну строку для AiRequestLog.error (≤500 chars)."""
    joined = " ; ".join(errors)
    return f"{prefix}: {joined}"[:500]


# ---- filtering and validation ------------------------------------------


def _filter_and_enrich(*, raw_items: list[Any], valid_ids: frozenset[int]) -> list[dict[str, Any]]:
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
            {"place_id": r.place_id, "reasoning": r.reasoning[:120]} for r in recommendations
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