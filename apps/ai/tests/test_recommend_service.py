# apps/ai/tests/test_recommend_service.py
"""
Тесты для recommend service.

LLMClient мокаем (нет реальных запросов в Gemini), БД настоящая.
Сервис async, тесты sync — оборачиваем вызов в async_to_sync. Это проще,
чем тащить @pytest.mark.asyncio и async-фабрики, и достаточно для покрытия
бизнес-логики.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from asgiref.sync import async_to_sync
from django.core.cache import cache

from apps.ai.clients.base import LLMError, LLMResponse
from apps.ai.models import AiRequestLog, AiRequestStatus
from apps.ai.services.exceptions import (
    AiInvalidResponse,
    AiNoValidPlaces,
    AiProviderError,
)
from apps.ai.services.recommend import recommend
from apps.places.models import City
from apps.places.tests.factories import PlaceFactory
from apps.users.tests.factories import UserFactory


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """Чистим Redis между тестами — иначе AI-context кэш протекает."""
    cache.clear()


def _llm_response(items: list[dict], *, model: str = "gemini-2.5-flash") -> LLMResponse:
    """Фабрика LLMResponse с валидным JSON-телом."""
    return LLMResponse(
        text=json.dumps({"items": items}),
        input_tokens=1000,
        output_tokens=200,
        model=model,
    )


def _patch_llm(mocker, *, response=None, side_effect=None) -> AsyncMock:  # type: ignore[no-untyped-def]
    """Мокает get_llm_client → клиент с заданным поведением complete()."""
    client_mock = AsyncMock()
    if side_effect is not None:
        client_mock.complete = AsyncMock(side_effect=side_effect)
    else:
        client_mock.complete = AsyncMock(return_value=response)
    mocker.patch("apps.ai.services.recommend.get_llm_client", return_value=client_mock)
    return client_mock


@pytest.mark.django_db
class TestRecommendService:
    def test_happy_path(self, mocker) -> None:  # type: ignore[no-untyped-def]
        user = UserFactory()
        places = [
            PlaceFactory(name=f"Place {i}", is_verified=True, city=City.ASTANA) for i in range(3)
        ]
        _patch_llm(
            mocker,
            response=_llm_response(
                [
                    {
                        "place_id": places[0].id,
                        "reasoning": "Тихое место для работы",
                        "vibe_match": ["calm", "productive"],
                    },
                    {
                        "place_id": places[1].id,
                        "reasoning": "Хорошие пирожки",
                        "vibe_match": ["calm"],
                    },
                ]
            ),
        )

        result = async_to_sync(recommend)(user_id=user.pk, query="куда пойти")

        assert len(result.items) == 2
        assert result.items[0].place_id == places[0].id
        assert result.items[0].name == "Place 0"
        assert result.items[0].reasoning == "Тихое место для работы"
        assert result.items[0].vibe_match == ["calm", "productive"]

        log = AiRequestLog.objects.get(pk=result.log_id)
        assert log.status == AiRequestStatus.OK
        assert log.input_tokens == 1000
        assert log.output_tokens == 200
        assert log.user_id == user.pk
        assert len(log.response_summary) == 2

    def test_hallucinated_place_id_filtered(self, mocker) -> None:  # type: ignore[no-untyped-def]
        user = UserFactory()
        real = PlaceFactory(is_verified=True, city=City.ASTANA)

        _patch_llm(
            mocker,
            response=_llm_response(
                [
                    {"place_id": 999999, "reasoning": "hallucinated"},
                    {"place_id": real.id, "reasoning": "real"},
                ]
            ),
        )

        result = async_to_sync(recommend)(user_id=user.pk, query="x")
        assert len(result.items) == 1
        assert result.items[0].place_id == real.id
        assert result.items[0].reasoning == "real"

    def test_all_hallucinated_raises(self, mocker) -> None:  # type: ignore[no-untyped-def]
        user = UserFactory()
        PlaceFactory(is_verified=True, city=City.ASTANA)

        _patch_llm(
            mocker,
            response=_llm_response([{"place_id": 999999, "reasoning": "x"}]),
        )

        with pytest.raises(AiNoValidPlaces):
            async_to_sync(recommend)(user_id=user.pk, query="x")

        log = AiRequestLog.objects.filter(user=user).first()
        assert log is not None
        assert log.status == AiRequestStatus.ERROR
        assert "no_valid_places_after_filter" in log.error

    def test_invalid_json_raises(self, mocker) -> None:  # type: ignore[no-untyped-def]
        user = UserFactory()
        PlaceFactory(is_verified=True, city=City.ASTANA)

        bad_response = LLMResponse(
            text="not a json {{{",
            input_tokens=10,
            output_tokens=5,
            model="gemini-2.5-flash",
        )
        _patch_llm(mocker, response=bad_response)

        with pytest.raises(AiInvalidResponse):
            async_to_sync(recommend)(user_id=user.pk, query="x")

        log = AiRequestLog.objects.filter(user=user).first()
        assert log is not None
        assert log.status == AiRequestStatus.ERROR
        assert "invalid_json" in log.error

    def test_llm_error_raises_provider_error(self, mocker) -> None:  # type: ignore[no-untyped-def]
        user = UserFactory()
        PlaceFactory(is_verified=True, city=City.ASTANA)

        _patch_llm(
            mocker,
            side_effect=LLMError("timeout", provider="gemini"),
        )

        with pytest.raises(AiProviderError):
            async_to_sync(recommend)(user_id=user.pk, query="x")

        log = AiRequestLog.objects.filter(user=user).first()
        assert log is not None
        assert log.status == AiRequestStatus.ERROR

    def test_duplicate_place_ids_dedup(self, mocker) -> None:  # type: ignore[no-untyped-def]
        """Если модель вернула один id дважды — оставляем первое вхождение."""
        user = UserFactory()
        p = PlaceFactory(is_verified=True, city=City.ASTANA)

        _patch_llm(
            mocker,
            response=_llm_response(
                [
                    {"place_id": p.id, "reasoning": "first"},
                    {"place_id": p.id, "reasoning": "second"},
                ]
            ),
        )

        result = async_to_sync(recommend)(user_id=user.pk, query="x")
        assert len(result.items) == 1
        assert result.items[0].reasoning == "first"

    def test_max_recommendations_truncated(self, mocker) -> None:  # type: ignore[no-untyped-def]
        """Если модель вернула 5+ — режем до MAX_RECOMMENDATIONS=3."""
        user = UserFactory()
        places = [PlaceFactory(is_verified=True, city=City.ASTANA) for _ in range(5)]

        _patch_llm(
            mocker,
            response=_llm_response(
                [{"place_id": p.id, "reasoning": f"r{i}"} for i, p in enumerate(places)]
            ),
        )

        result = async_to_sync(recommend)(user_id=user.pk, query="x")
        assert len(result.items) == 3

    def test_user_preferences_passed_to_prompt(self, mocker) -> None:  # type: ignore[no-untyped-def]
        """preferred_vibes и ai_context подмешиваются в user message."""
        user = UserFactory(
            preferred_vibes=["calm", "productive"],
            ai_context="вегетарианец",
        )
        place = PlaceFactory(is_verified=True, city=City.ASTANA)

        client_mock = _patch_llm(
            mocker,
            response=_llm_response([{"place_id": place.id, "reasoning": "ok"}]),
        )

        async_to_sync(recommend)(user_id=user.pk, query="куда поработать")

        # Проверяем что в user message прилетели вайбы и ai_context.
        call_kwargs = client_mock.complete.call_args.kwargs
        user_msg = call_kwargs["messages"][0].content
        assert "calm" in user_msg
        assert "productive" in user_msg
        assert "вегетарианец" in user_msg
        assert "куда поработать" in user_msg

    def test_empty_vibe_match_handled(self, mocker) -> None:  # type: ignore[no-untyped-def]
        """vibe_match может отсутствовать в ответе модели — это ок."""
        user = UserFactory()
        place = PlaceFactory(is_verified=True, city=City.ASTANA)

        _patch_llm(
            mocker,
            response=_llm_response(
                [{"place_id": place.id, "reasoning": "ok"}]  # без vibe_match
            ),
        )

        result = async_to_sync(recommend)(user_id=user.pk, query="x")
        assert len(result.items) == 1
        assert result.items[0].vibe_match == []

    def test_cost_calculated_in_log(self, mocker) -> None:  # type: ignore[no-untyped-def]
        """В лог пишется cost_usd, рассчитанный по тарифу модели."""
        user = UserFactory()
        place = PlaceFactory(is_verified=True, city=City.ASTANA)

        _patch_llm(
            mocker,
            response=_llm_response(
                [{"place_id": place.id, "reasoning": "ok"}],
                model="gemini-2.5-flash",
            ),
        )

        result = async_to_sync(recommend)(user_id=user.pk, query="x")
        log = AiRequestLog.objects.get(pk=result.log_id)
        # gemini-2.5-flash: $0.30/1M in × 1000 + $2.50/1M out × 200
        # = 0.0003 + 0.0005 = 0.0008
        assert log.cost_usd > 0
        assert log.model == "gemini-2.5-flash"
