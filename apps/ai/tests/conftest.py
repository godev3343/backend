"""
Локальные фикстуры для AI-тестов.

_clear_cache (autouse) — в cache живут:
- AI-context кэш (ai:context:{city}:v{N}) и счётчик ai:vibes_version
- DRF throttle counters (AiRecommendThrottle, 10/час)
Без сброса тесты на endpoint флакают после ~10 прогонов, а тесты
context builder начинают видеть результаты соседних тестов через cache hit.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


@pytest.fixture(autouse=True)
def _clear_cache():  # type: ignore[no-untyped-def]
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def user_factory(db) -> Callable[..., AbstractUser]:  # type: ignore[no-untyped-def]
    from apps.users.tests.factories import UserFactory

    return UserFactory


@pytest.fixture
def user(user_factory: Callable[..., AbstractUser]) -> AbstractUser:
    return user_factory()


@pytest.fixture
def authed_client(api_client: APIClient, user: AbstractUser) -> APIClient:
    """API client с JWT текущего пользователя."""
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return api_client


@pytest.fixture
def onboarded_user(user_factory: Callable[..., AbstractUser]) -> AbstractUser:
    """Юзер с заполненным display_name и consent_at — проходит IsOnboarded."""
    from django.utils.timezone import now

    return user_factory(display_name="Tester", consent_at=now())


@pytest.fixture
def onboarded_client(api_client: APIClient, onboarded_user: AbstractUser) -> APIClient:
    refresh = RefreshToken.for_user(onboarded_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return api_client
