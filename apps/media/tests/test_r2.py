"""Smoke-тесты apps.media.r2 — проверка контракта функций."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.media.r2 import (
    R2Error,
    R2ObjectNotFound,
    build_public_url,
    delete_object,
    delete_objects,
    download_to_bytes,
    generate_presigned_put,
    head_object,
    upload_bytes,
)


@pytest.fixture
def boto_client():
    """Мокаем boto3-клиент целиком — обнуляем lru_cache между тестами."""
    from apps.media import r2

    r2._get_client.cache_clear()
    client = MagicMock()
    with patch("apps.media.r2._get_client", return_value=client):
        yield client
    r2._get_client.cache_clear()


class TestPresign:
    def test_calls_generate_presigned_url(self, boto_client) -> None:  # type: ignore[no-untyped-def]
        boto_client.generate_presigned_url.return_value = "https://signed.url"
        url = generate_presigned_put(
            key="k", content_type="image/jpeg", content_length=100
        )
        assert url == "https://signed.url"
        boto_client.generate_presigned_url.assert_called_once()
        call_kw = boto_client.generate_presigned_url.call_args.kwargs
        assert call_kw["Params"]["Key"] == "k"
        assert call_kw["Params"]["ContentType"] == "image/jpeg"
        assert call_kw["Params"]["ContentLength"] == 100
        assert call_kw["HttpMethod"] == "PUT"


class TestHead:
    def test_returns_normalized_metadata(self, boto_client) -> None:  # type: ignore[no-untyped-def]
        boto_client.head_object.return_value = {
            "ContentLength": 500,
            "ContentType": "image/png",
            "ETag": '"abc"',
        }
        meta = head_object("some/key.png")
        assert meta == {
            "content_length": 500,
            "content_type": "image/png",
            "etag": "abc",
        }

    def test_404_raises_not_found(self, boto_client) -> None:  # type: ignore[no-untyped-def]
        from botocore.exceptions import ClientError

        boto_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404"}}, "HeadObject"
        )
        with pytest.raises(R2ObjectNotFound):
            head_object("missing/key")


class TestDelete:
    def test_delete_no_keys_is_noop(self, boto_client) -> None:  # type: ignore[no-untyped-def]
        delete_objects([])
        boto_client.delete_objects.assert_not_called()

    def test_delete_bulk(self, boto_client) -> None:  # type: ignore[no-untyped-def]
        delete_objects(["a", "b", "c"])
        boto_client.delete_objects.assert_called_once()
        call_kw = boto_client.delete_objects.call_args.kwargs
        keys_in_call = [o["Key"] for o in call_kw["Delete"]["Objects"]]
        assert keys_in_call == ["a", "b", "c"]

    def test_bulk_max_1000(self, boto_client) -> None:  # type: ignore[no-untyped-def]
        with pytest.raises(R2Error):
            delete_objects([f"k{i}" for i in range(1001)])


class TestPublicUrl:
    def test_builds_url(self, settings) -> None:  # type: ignore[no-untyped-def]
        settings.R2_PUBLIC_URL = "https://cdn.example.com"
        assert build_public_url("avatars/1/x/y.jpg") == (
            "https://cdn.example.com/avatars/1/x/y.jpg"
        )

    def test_empty_public_url_raises(self, settings) -> None:  # type: ignore[no-untyped-def]
        settings.R2_PUBLIC_URL = ""
        with pytest.raises(R2Error):
            build_public_url("k")