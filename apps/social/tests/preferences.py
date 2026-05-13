"""
Тесты для PUT /api/users/me/preferences и для AI-полей в PATCH /api/users/me.
"""
from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.places.models import PlaceVibeTag
from apps.users.tests.factories import UserFactory


@pytest.fixture
def authed_client(db) -> tuple[APIClient, "User"]:  # type: ignore[no-untyped-def]
    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


class TestPreferencesPut:
    """PUT /api/users/me/preferences — атомарная замена AI-настроек."""

    def test_unauthenticated_returns_401(self, db) -> None:
        client = APIClient()
        url = reverse("social:user_me_preferences")
        response = client.put(url, data={"preferred_vibes": [], "ai_context": ""}, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_valid_preferences_saved(self, authed_client) -> None:  # type: ignore[no-untyped-def]
        client, user = authed_client
        url = reverse("social:user_me_preferences")

        payload = {
            "preferred_vibes": [PlaceVibeTag.CALM, PlaceVibeTag.PRODUCTIVE],
            "ai_context": "Вегетарианец, работаю удалённо",
        }
        response = client.put(url, data=payload, format="json")
        assert response.status_code == status.HTTP_200_OK

        user.refresh_from_db()
        assert user.preferred_vibes == ["calm", "productive"]
        assert user.ai_context == "Вегетарианец, работаю удалённо"

    def test_empty_payload_is_valid_clears_settings(self, authed_client) -> None:  # type: ignore[no-untyped-def]
        client, user = authed_client
        user.preferred_vibes = ["calm"]
        user.ai_context = "что-то"
        user.save(update_fields=["preferred_vibes", "ai_context"])

        url = reverse("social:user_me_preferences")
        response = client.put(
            url,
            data={"preferred_vibes": [], "ai_context": ""},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

        user.refresh_from_db()
        assert user.preferred_vibes == []
        assert user.ai_context == ""

    def test_invalid_vibe_rejected(self, authed_client) -> None:  # type: ignore[no-untyped-def]
        client, _ = authed_client
        url = reverse("social:user_me_preferences")

        response = client.put(
            url,
            data={"preferred_vibes": ["not_a_real_vibe"], "ai_context": ""},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_duplicate_vibes_rejected(self, authed_client) -> None:  # type: ignore[no-untyped-def]
        client, _ = authed_client
        url = reverse("social:user_me_preferences")

        response = client.put(
            url,
            data={
                "preferred_vibes": [PlaceVibeTag.CALM, PlaceVibeTag.CALM],
                "ai_context": "",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_too_many_vibes_rejected(self, authed_client) -> None:  # type: ignore[no-untyped-def]
        client, _ = authed_client
        url = reverse("social:user_me_preferences")

        # Все 7 вайбов — больше лимита в 5
        all_vibes = [v.value for v in PlaceVibeTag]
        response = client.put(
            url,
            data={"preferred_vibes": all_vibes, "ai_context": ""},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_ai_context_too_long_rejected(self, authed_client) -> None:  # type: ignore[no-untyped-def]
        client, _ = authed_client
        url = reverse("social:user_me_preferences")

        response = client.put(
            url,
            data={"preferred_vibes": [], "ai_context": "x" * 501},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_put_is_idempotent(self, authed_client) -> None:  # type: ignore[no-untyped-def]
        """Повторный PUT с тем же payload даёт тот же результат, не ошибку."""
        client, user = authed_client
        url = reverse("social:user_me_preferences")
        payload = {
            "preferred_vibes": [PlaceVibeTag.ACTIVE],
            "ai_context": "люблю шумные места",
        }

        r1 = client.put(url, data=payload, format="json")
        r2 = client.put(url, data=payload, format="json")

        assert r1.status_code == status.HTTP_200_OK
        assert r2.status_code == status.HTTP_200_OK

        user.refresh_from_db()
        assert user.preferred_vibes == ["active"]


class TestPatchMeWithAiFields:
    """PATCH /api/users/me принимает preferred_vibes и ai_context частично."""

    def test_patch_only_vibes(self, authed_client) -> None:  # type: ignore[no-untyped-def]
        client, user = authed_client
        user.bio = "старое био"
        user.save(update_fields=["bio"])

        url = reverse("social:user_me")
        response = client.patch(
            url,
            data={"preferred_vibes": [PlaceVibeTag.NETWORKING]},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

        user.refresh_from_db()
        assert user.preferred_vibes == ["networking"]
        assert user.bio == "старое био"  # не затёрто

    def test_patch_ai_context_only(self, authed_client) -> None:  # type: ignore[no-untyped-def]
        client, user = authed_client
        url = reverse("social:user_me")
        response = client.patch(
            url, data={"ai_context": "новый контекст"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.ai_context == "новый контекст"

    def test_get_me_includes_ai_fields(self, authed_client) -> None:  # type: ignore[no-untyped-def]
        client, user = authed_client
        user.preferred_vibes = ["calm", "romantic"]
        user.ai_context = "abc"
        user.save(update_fields=["preferred_vibes", "ai_context"])

        url = reverse("social:user_me")
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["preferred_vibes"] == ["calm", "romantic"]
        assert body["ai_context"] == "abc"