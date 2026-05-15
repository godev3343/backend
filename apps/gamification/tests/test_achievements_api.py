"""GET /api/users/me/achievements."""
from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.gamification.models import Achievement, UserAchievement
from apps.users.tests.factories import UserFactory


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.mark.django_db
class TestMyAchievements:
    def test_empty(self) -> None:
        user = UserFactory()
        api = APIClient()
        api.force_authenticate(user=user)

        resp = api.get(reverse("gamification:me-achievements"))

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data == []

    def test_returns_unlocked(self) -> None:
        user = UserFactory()
        a1 = Achievement.objects.create(
            code="pioneer", name_ru="Первооткрыватель",
            description_ru="...", order=10,
        )
        a2 = Achievement.objects.create(
            code="critic", name_ru="Критик",
            description_ru="...", order=20,
        )
        UserAchievement.objects.create(user=user, achievement=a1)
        UserAchievement.objects.create(user=user, achievement=a2)

        api = APIClient()
        api.force_authenticate(user=user)
        resp = api.get(reverse("gamification:me-achievements"))

        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) == 2
        codes = [item["achievement"]["code"] for item in resp.data]
        assert codes == ["pioneer", "critic"]  # по order

    def test_only_own(self) -> None:
        me = UserFactory()
        other = UserFactory()
        a = Achievement.objects.create(
            code="pioneer", name_ru="...", description_ru="...",
        )
        UserAchievement.objects.create(user=other, achievement=a)

        api = APIClient()
        api.force_authenticate(user=me)
        resp = api.get(reverse("gamification:me-achievements"))

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data == []

    def test_anon_401(self, api_client: APIClient) -> None:
        resp = api_client.get(reverse("gamification:me-achievements"))
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED