"""HTTP-тесты media-эндпоинтов."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils.timezone import now
from rest_framework import status
from rest_framework.test import APIClient

from apps.media.tests.factories import MediaAssetFactory
from apps.users.tests.factories import UserFactory


def _verified_user(**kwargs):  # type: ignore[no-untyped-def]
    """Юзер с подтверждённым email — нужно для IsEmailVerified."""
    defaults = {
        "email_verified_at": now(),
        "display_name": kwargs.pop("display_name", "u"),
    }
    defaults.update(kwargs)
    return UserFactory(**defaults)


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.mark.django_db
class TestPresignEndpoint:
    def test_happy_path(self, client: APIClient, r2_mock) -> None:  # type: ignore[no-untyped-def]
        user = _verified_user()
        client.force_authenticate(user)
        resp = client.post(
            reverse("media:upload_presign"),
            {
                "purpose": "avatar",
                "content_type": "image/jpeg",
                "content_length": 50_000,
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        body = resp.json()
        assert body["asset_id"]
        assert body["upload_url"].startswith("https://")
        assert body["key"].startswith(f"avatars/{user.pk}/")
        assert body["expires_in"] > 0

    def test_unauthenticated(self, client: APIClient) -> None:
        resp = client.post(
            reverse("media:upload_presign"),
            {
                "purpose": "avatar",
                "content_type": "image/jpeg",
                "content_length": 100,
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unverified_email_forbidden(self, client: APIClient, r2_mock) -> None:  # type: ignore[no-untyped-def]
        user = UserFactory(email_verified_at=None, display_name="x")
        client.force_authenticate(user)
        resp = client.post(
            reverse("media:upload_presign"),
            {
                "purpose": "avatar",
                "content_type": "image/jpeg",
                "content_length": 100,
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_invalid_purpose(self, client: APIClient, r2_mock) -> None:  # type: ignore[no-untyped-def]
        user = _verified_user()
        client.force_authenticate(user)
        resp = client.post(
            reverse("media:upload_presign"),
            {
                "purpose": "unknown",
                "content_type": "image/jpeg",
                "content_length": 100,
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_invalid_content_type(self, client: APIClient, r2_mock) -> None:  # type: ignore[no-untyped-def]
        user = _verified_user()
        client.force_authenticate(user)
        resp = client.post(
            reverse("media:upload_presign"),
            {
                "purpose": "avatar",
                "content_type": "image/gif",
                "content_length": 100,
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_too_large(self, client: APIClient, r2_mock, settings) -> None:  # type: ignore[no-untyped-def]
        user = _verified_user()
        client.force_authenticate(user)
        resp = client.post(
            reverse("media:upload_presign"),
            {
                "purpose": "avatar",
                "content_type": "image/jpeg",
                "content_length": settings.UPLOAD_MAX_SIZE["avatar"] + 1,
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        assert resp.json()["code"] == "file_too_large"

    def test_negative_size_400(self, client: APIClient, r2_mock) -> None:  # type: ignore[no-untyped-def]
        user = _verified_user()
        client.force_authenticate(user)
        resp = client.post(
            reverse("media:upload_presign"),
            {
                "purpose": "avatar",
                "content_type": "image/jpeg",
                "content_length": -1,
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestConfirmEndpoint:
    def test_happy_path(self, client: APIClient, r2_mock, celery_eager) -> None:  # type: ignore[no-untyped-def]
        user = _verified_user()
        asset = MediaAssetFactory(owner=user)
        client.force_authenticate(user)

        with patch("apps.media.services.upload.process_image") as task_mock:
            task_mock.apply_async.return_value.id = "t1"
            resp = client.post(
                reverse("media:upload_confirm"),
                {"asset_id": asset.pk},
                format="json",
            )

        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["id"] == asset.pk
        assert body["status"] == "pending"
        assert body["url_original"]

    def test_unknown_asset_404(self, client: APIClient, r2_mock) -> None:  # type: ignore[no-untyped-def]
        user = _verified_user()
        client.force_authenticate(user)
        resp = client.post(
            reverse("media:upload_confirm"),
            {"asset_id": 999_999},
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert resp.json()["code"] == "media_asset_not_found"

    def test_other_users_asset_403(self, client: APIClient, r2_mock) -> None:  # type: ignore[no-untyped-def]
        owner = _verified_user(display_name="owner")
        stranger = _verified_user(display_name="stranger")
        asset = MediaAssetFactory(owner=owner)
        client.force_authenticate(stranger)
        resp = client.post(
            reverse("media:upload_confirm"),
            {"asset_id": asset.pk},
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestMediaAssetDetailEndpoint:
    def test_get_own_asset(self, client: APIClient) -> None:
        user = _verified_user()
        asset = MediaAssetFactory(owner=user)
        client.force_authenticate(user)
        resp = client.get(reverse("media:media_detail", args=[asset.pk]))
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["id"] == asset.pk

    def test_get_others_asset_404(self, client: APIClient) -> None:
        owner = _verified_user()
        stranger = _verified_user()
        asset = MediaAssetFactory(owner=owner)
        client.force_authenticate(stranger)
        resp = client.get(reverse("media:media_detail", args=[asset.pk]))
        # 404, не 403 — не подтверждаем существование чужого asset id
        assert resp.status_code == status.HTTP_404_NOT_FOUND
