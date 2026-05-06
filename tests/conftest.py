"""Глобальные фикстуры pytest."""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def authed_client(api_client: APIClient, user) -> APIClient:
    """API client с JWT текущего пользователя."""
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return api_client


@pytest.fixture
def user(db, user_factory):
    return user_factory()


@pytest.fixture
def user_factory(db):
    """Импортируется из apps/users/tests/factories.py.
    На этом этапе ещё нет — вернём заглушку, дополним в EPIC 1.
    """
    from apps.users.tests.factories import UserFactory
    return UserFactory