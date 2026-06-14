"""Создание поста с медиа из ключей media-пайплайна."""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.media.models import MediaPurpose, MediaStatus
from apps.media.tests.factories import MediaAssetFactory


@pytest.fixture(autouse=True)
def _r2_public(settings):  # type: ignore[no-untyped-def]
    settings.R2_PUBLIC_URL = "https://cdn.test"


@pytest.mark.django_db
class TestCreatePostWithMedia:
    def test_image_media_builds_url_and_aspect(self, authed_client, user) -> None:
        asset = MediaAssetFactory(
            owner=user,
            purpose=MediaPurpose.POST_IMAGE,
            status=MediaStatus.PROCESSED,
            key_original="post_images/1/abc/original.jpg",
            key_feed="post_images/1/abc/feed.webp",
            width=800,
            height=1000,
        )
        resp = authed_client.post(
            reverse("community:post_list_create"),
            {
                "text": "with photo",
                "media": [{"type": "image", "key": asset.key_original}],
            },
            format="json",
        )
        assert resp.status_code == 201, resp.data
        media = resp.data["media"]
        assert len(media) == 1
        assert media[0]["type"] == "image"
        assert media[0]["url"].endswith("feed.webp")
        assert media[0]["thumbnail_url"] == ""
        assert media[0]["aspect_ratio"] == pytest.approx(0.8)

    def test_media_not_ready_rejected(self, authed_client, user) -> None:
        asset = MediaAssetFactory(
            owner=user,
            purpose=MediaPurpose.POST_IMAGE,
            status=MediaStatus.PENDING,
            key_original="post_images/1/zzz/original.jpg",
        )
        resp = authed_client.post(
            reverse("community:post_list_create"),
            {"media": [{"type": "image", "key": asset.key_original}]},
            format="json",
        )
        assert resp.status_code == 400
        assert resp.data["code"] == "post_media_not_ready"

    def test_media_not_owned_rejected(self, authed_client, another_user) -> None:
        asset = MediaAssetFactory(
            owner=another_user,
            purpose=MediaPurpose.POST_IMAGE,
            status=MediaStatus.PROCESSED,
            key_original="post_images/2/own/original.jpg",
            key_feed="post_images/2/own/feed.webp",
        )
        resp = authed_client.post(
            reverse("community:post_list_create"),
            {"media": [{"type": "image", "key": asset.key_original}]},
            format="json",
        )
        assert resp.status_code == 400
        assert resp.data["code"] == "post_media_not_found"

    def test_wrong_type_rejected(self, authed_client, user) -> None:
        # asset загружен как image, но в посте указан video → purpose mismatch.
        asset = MediaAssetFactory(
            owner=user,
            purpose=MediaPurpose.POST_IMAGE,
            status=MediaStatus.PROCESSED,
            key_original="post_images/1/mismatch/original.jpg",
            key_feed="post_images/1/mismatch/feed.webp",
        )
        resp = authed_client.post(
            reverse("community:post_list_create"),
            {"media": [{"type": "video", "key": asset.key_original}]},
            format="json",
        )
        assert resp.status_code == 400
        assert resp.data["code"] == "post_media_not_found"
