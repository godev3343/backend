# apps/users/tests/test_auth_google.py
"""Тесты Google OAuth с моком id_token.verify_oauth2_token."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def google_configured(settings):  # type: ignore[no-untyped-def]
    """Подменяет GOOGLE_OAUTH_CLIENT_IDS на тестовый client_id."""
    settings.GOOGLE_OAUTH_CLIENT_IDS = ["client-id-from-settings"]
    return settings


def _google_payload(**overrides) -> dict:  # type: ignore[no-untyped-def]
    base = {
        "sub": "google-sub-12345",
        "aud": "client-id-from-settings",
        "email": "google@test.local",
        "email_verified": True,
        "given_name": "Иван",
        "family_name": "Петров",
        "picture": "https://example.com/avatar.jpg",
    }
    base.update(overrides)
    return base


@pytest.mark.django_db
class TestGoogleAuth:
    def test_new_user_created(self, client: APIClient, google_configured) -> None:
        with patch(
            "apps.users.services.google.google_id_token.verify_oauth2_token",
            return_value=_google_payload(),
        ):
            resp = client.post(
                reverse("users:google_auth"),
                {"id_token": "fake-token"},
                format="json",
            )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["created"] is True
        assert "access" in data and "refresh" in data

        user = User.objects.get(email="google@test.local")
        assert user.google_sub == "google-sub-12345"
        assert user.is_email_verified is True

    def test_existing_user_linked_by_email(self, client: APIClient, google_configured) -> None:
        existing = User.objects.create_user(
            email="google@test.local", first_name="X", password="pass-12345"
        )
        assert existing.google_sub is None

        with patch(
            "apps.users.services.google.google_id_token.verify_oauth2_token",
            return_value=_google_payload(),
        ):
            resp = client.post(
                reverse("users:google_auth"),
                {"id_token": "fake-token"},
                format="json",
            )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["created"] is False

        existing.refresh_from_db()
        assert existing.google_sub == "google-sub-12345"
        assert existing.is_email_verified is True

    def test_returning_user_by_sub(self, client: APIClient, google_configured) -> None:
        existing = User.objects.create_user(
            email="other-email@test.local",
            first_name="X",
            password="pass-12345",
            google_sub="google-sub-12345",
        )

        with patch(
            "apps.users.services.google.google_id_token.verify_oauth2_token",
            return_value=_google_payload(email="changed@test.local"),
        ):
            resp = client.post(
                reverse("users:google_auth"),
                {"id_token": "fake-token"},
                format="json",
            )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["created"] is False
        # Email не меняем — приоритет у локальной БД
        existing.refresh_from_db()
        assert existing.email == "other-email@test.local"

    def test_invalid_aud(self, client: APIClient, google_configured) -> None:
        with patch(
            "apps.users.services.google.google_id_token.verify_oauth2_token",
            return_value=_google_payload(aud="some-other-client"),
        ):
            resp = client.post(
                reverse("users:google_auth"),
                {"id_token": "fake-token"},
                format="json",
            )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.json()["code"] == "invalid_audience"

    def test_invalid_token(self, client: APIClient, google_configured) -> None:
        with patch(
            "apps.users.services.google.google_id_token.verify_oauth2_token",
            side_effect=ValueError("bad token"),
        ):
            resp = client.post(
                reverse("users:google_auth"),
                {"id_token": "fake-token"},
                format="json",
            )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.json()["code"] == "invalid_id_token"

    def test_email_not_verified_at_google(self, client: APIClient, google_configured) -> None:
        with patch(
            "apps.users.services.google.google_id_token.verify_oauth2_token",
            return_value=_google_payload(email_verified=False),
        ):
            resp = client.post(
                reverse("users:google_auth"),
                {"id_token": "fake-token"},
                format="json",
            )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.json()["code"] == "google_email_unverified"


@pytest.mark.django_db
def test_google_not_configured(client: APIClient, settings) -> None:
    """Если client_ids пуст — endpoint падает."""
    settings.GOOGLE_OAUTH_CLIENT_IDS = []
    resp = client.post(
        reverse("users:google_auth"),
        {"id_token": "fake-token"},
        format="json",
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert resp.json()["code"] == "google_not_configured"
