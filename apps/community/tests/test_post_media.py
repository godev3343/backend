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

    def test_image_key_survives_original_rewrite(self, authed_client, user) -> None:
        # Бэкенд переписал оригинал в webp при даунскейле; клиент шлёт исходный
        # presign-ключ (.jpg). Резолв по префиксу всё равно находит ассет.
        asset = MediaAssetFactory(
            owner=user,
            purpose=MediaPurpose.POST_IMAGE,
            status=MediaStatus.PROCESSED,
            key_original="post_images/1/rewritten/original.webp",
            key_feed="post_images/1/rewritten/feed.webp",
            width=800,
            height=1000,
        )
        presign_key = "post_images/1/rewritten/original.jpg"
        resp = authed_client.post(
            reverse("community:post_list_create"),
            {"media": [{"type": "image", "key": presign_key}]},
            format="json",
        )
        assert resp.status_code == 201, resp.data
        assert resp.data["media"][0]["url"].endswith("feed.webp")
        assert asset.key_original  # sanity: ассет существует

    def test_video_media_uses_poster_thumbnail(self, authed_client, user) -> None:
        # process_video кладёт постер в key_feed; url видео = оригинал mp4.
        asset = MediaAssetFactory(
            owner=user,
            purpose=MediaPurpose.POST_VIDEO,
            status=MediaStatus.PROCESSED,
            key_original="post_videos/1/v/original.mp4",
            key_feed="post_videos/1/v/feed.webp",
            key_thumb="post_videos/1/v/thumb.webp",
            width=1280,
            height=720,
        )
        resp = authed_client.post(
            reverse("community:post_list_create"),
            {"media": [{"type": "video", "key": asset.key_original}]},
            format="json",
        )
        assert resp.status_code == 201, resp.data
        media = resp.data["media"][0]
        assert media["type"] == "video"
        assert media["url"].endswith("original.mp4")
        assert media["thumbnail_url"].endswith("feed.webp")
        assert media["aspect_ratio"] == pytest.approx(1280 / 720, abs=1e-3)

    def test_video_media_not_ready_rejected(self, authed_client, user) -> None:
        # Вариант А: пока постер не готов (PENDING) — пост создать нельзя.
        asset = MediaAssetFactory(
            owner=user,
            purpose=MediaPurpose.POST_VIDEO,
            status=MediaStatus.PENDING,
            key_original="post_videos/1/pending/original.mp4",
        )
        resp = authed_client.post(
            reverse("community:post_list_create"),
            {"media": [{"type": "video", "key": asset.key_original}]},
            format="json",
        )
        assert resp.status_code == 400
        assert resp.data["code"] == "post_media_not_ready"

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
