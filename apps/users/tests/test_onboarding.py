"""Тесты онбординга."""
from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.tests.factories import UserFactory


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def authed_client(client: APIClient) -> tuple[APIClient, object]:
    user = UserFactory(display_name="", consent_at=None)
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client, user


@pytest.mark.django_db
class TestOnboarding:
    def test_anonymous_blocked(self, client: APIClient) -> None:
        resp = client.post(reverse("users:onboarding"), {}, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_minimal_success(self, authed_client: tuple[APIClient, object]) -> None:
        client, user = authed_client
        resp = client.post(
            reverse("users:onboarding"),
            {"display_name": "alice", "consent": True},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["display_name"] == "alice"
        assert body["is_onboarded"] is True

        user.refresh_from_db()  # type: ignore[attr-defined]
        assert user.display_name == "alice"  # type: ignore[attr-defined]
        assert user.consent_at is not None  # type: ignore[attr-defined]

    def test_consent_required(self, authed_client: tuple[APIClient, object]) -> None:
        client, _ = authed_client
        resp = client.post(
            reverse("users:onboarding"),
            {"display_name": "alice", "consent": False},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_short_display_name(
        self, authed_client: tuple[APIClient, object]
    ) -> None:
        client, _ = authed_client
        resp = client.post(
            reverse("users:onboarding"),
            {"display_name": "a", "consent": True},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_idempotent_repeat(
        self, authed_client: tuple[APIClient, object]
    ) -> None:
        client, _ = authed_client
        client.post(
            reverse("users:onboarding"),
            {"display_name": "alice", "consent": True},
            format="json",
        )
        resp = client.post(
            reverse("users:onboarding"),
            {"display_name": "alice2", "bio": "hi", "consent": True},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["display_name"] == "alice2"
        assert resp.json()["bio"] == "hi"