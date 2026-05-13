"""
GET /api/users/me/points — история начислений текущего юзера.

Поведение:
- 401 для анонима
- свои транзакции отдаются, чужие нет
- сортировка по created_at DESC (новые сверху)
- cursor-пагинация по 50 на страницу
"""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.gamification.models import PointsReason
from apps.gamification.services import PointsService
from apps.users.tests.factories import UserFactory


URL = "/api/users/me/points"


@pytest.mark.django_db
class TestMyPointsHistoryView:
    def test_anonymous_unauthorized(self) -> None:
        client = APIClient()
        response = client.get(URL)
        assert response.status_code == 401

    def test_returns_own_transactions(self) -> None:
        user = UserFactory()
        PointsService.award(
            user=user, reason=PointsReason.CHECKIN,
            ref_type="checkin", ref_id=1,
        )
        PointsService.award(
            user=user, reason=PointsReason.FIRST_CHECKIN,
            ref_type="checkin", ref_id=1,
        )
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get(URL)
        assert response.status_code == 200
        results = response.data["results"]
        assert len(results) == 2
        reasons = {r["reason"] for r in results}
        assert reasons == {"checkin", "first_checkin"}

    def test_does_not_leak_other_users_transactions(self) -> None:
        me = UserFactory()
        other = UserFactory()
        PointsService.award(
            user=other, reason=PointsReason.CHECKIN,
            ref_type="checkin", ref_id=999,
        )
        client = APIClient()
        client.force_authenticate(user=me)
        response = client.get(URL)
        assert response.status_code == 200
        assert response.data["results"] == []

    def test_ordering_newest_first(self) -> None:
        user = UserFactory()
        # Создаём транзакции с разными ref_id — порядок создания = порядок created_at
        first = PointsService.award(
            user=user, reason=PointsReason.CHECKIN,
            ref_type="checkin", ref_id=1,
        )
        second = PointsService.award(
            user=user, reason=PointsReason.CHECKIN,
            ref_type="checkin", ref_id=2,
        )
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get(URL)
        results = response.data["results"]
        assert results[0]["id"] == second.pk
        assert results[1]["id"] == first.pk

    def test_pagination_50_per_page(self) -> None:
        user = UserFactory()
        for i in range(55):
            PointsService.award(
                user=user, reason=PointsReason.CHECKIN,
                ref_type="checkin", ref_id=i,
            )
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get(URL)
        assert len(response.data["results"]) == 50
        assert response.data["next"] is not None

        # Следующая страница
        next_url = response.data["next"]
        response2 = client.get(next_url)
        assert response2.status_code == 200
        assert len(response2.data["results"]) == 5
        assert response2.data["next"] is None

    def test_serialized_fields(self) -> None:
        user = UserFactory()
        tx = PointsService.award(
            user=user, reason=PointsReason.FRIEND_ADDED,
            ref_type="friendship", ref_id=42,
        )
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get(URL)
        item = response.data["results"][0]
        assert set(item.keys()) == {
            "id", "delta", "reason", "ref_type", "ref_id", "created_at"
        }
        assert item["id"] == tx.pk
        assert item["delta"] == 5
        assert item["reason"] == "friend_added"
        assert item["ref_type"] == "friendship"
        assert item["ref_id"] == 42