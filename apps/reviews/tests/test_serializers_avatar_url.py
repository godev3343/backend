"""
Регрессия: avatar_url в payload отзыва должен быть null для юзеров
без аватара, не пустой строкой (бэк-долг #8).

User.avatar_url (@property) возвращает "" — это исторический контракт,
ломать его не хочется. Точечная нормализация в ReviewSerializer.get_user.
"""

from __future__ import annotations

import pytest
from django.urls import reverse
from django.utils.timezone import now
from rest_framework import status
from rest_framework.test import APIClient

from apps.places.tests.factories import PlaceFactory
from apps.reviews.tests.factories import ReviewFactory
from apps.users.tests.factories import UserFactory


def _verified_user(**kwargs):  # type: ignore[no-untyped-def]
    return UserFactory(email_verified_at=now(), **kwargs)


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.mark.django_db
class TestReviewAvatarUrlNormalization:
    """Контракт: avatar_url либо null, либо непустой URL. Никаких "" в payload."""

    def test_user_without_avatar_returns_null(self, api_client: APIClient) -> None:
        """Юзер без avatar_asset → avatar_url в payload = null."""
        author = _verified_user()
        assert author.avatar_asset_id is None  # sanity: фабрика не создаёт asset

        place = PlaceFactory()
        ReviewFactory(user=author, place=place)

        url = reverse("reviews:place-reviews", kwargs={"place_id": place.pk})
        resp = api_client.get(url)

        assert resp.status_code == status.HTTP_200_OK
        results = resp.data["results"]
        assert len(results) == 1
        user_payload = results[0]["user"]
        assert user_payload["avatar_url"] is None
        # И защищаемся от регрессии: на всякий случай явно проверим, что не ""
        assert user_payload["avatar_url"] != ""

    def test_payload_user_shape(self, api_client: APIClient) -> None:
        """Контрактный тест: user-блок содержит id, public_name, avatar_url."""
        author = _verified_user(display_name="Aida Test")
        place = PlaceFactory()
        ReviewFactory(user=author, place=place)

        url = reverse("reviews:place-reviews", kwargs={"place_id": place.pk})
        resp = api_client.get(url)

        user_payload = resp.data["results"][0]["user"]
        assert set(user_payload.keys()) == {"id", "public_name", "avatar_url"}
        assert user_payload["id"] == author.pk
        assert user_payload["public_name"] == "Aida Test"