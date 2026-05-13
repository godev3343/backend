"""
Локальные фикстуры для geocoding-тестов.

api_client / authed_client — для GET /api/geocode (IsAuthenticated).
_clear_cache (autouse) — геокодинг кэшируется в Redis на 24ч;
без сброса между тестами cache hit маскирует регрессии в Mapbox-клиенте.
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
