"""Юнит-тесты генерации R2-ключей."""
from __future__ import annotations

import pytest

from apps.media.models import MediaPurpose
from apps.media.services.keys import (
    CONTENT_TYPE_TO_EXT,
    build_original_key,
    build_variant_key,
    is_safe_key,
    is_supported_content_type,
    known_purpose_from_key,
    new_asset_uuid,
    parse_owner_id_from_key,
)


class TestContentType:
    @pytest.mark.parametrize(
        "ct,expected",
        [
            ("image/jpeg", True),
            ("image/png", True),
            ("image/webp", True),
            ("image/heic", True),
            ("image/heif", True),
            ("image/gif", False),
            ("image/svg+xml", False),
            ("application/pdf", False),
            ("", False),
        ],
    )
    def test_is_supported(self, ct: str, expected: bool) -> None:
        assert is_supported_content_type(ct) is expected


class TestKeys:
    def test_original_key_structure(self) -> None:
        key = build_original_key(
            purpose=MediaPurpose.AVATAR,
            owner_id=42,
            asset_uuid="abc123",
            content_type="image/jpeg",
        )
        assert key == "avatars/42/abc123/original.jpg"

    def test_original_key_heic(self) -> None:
        key = build_original_key(
            purpose=MediaPurpose.CHECKIN,
            owner_id=1,
            asset_uuid="xyz",
            content_type="image/heic",
        )
        assert key == "checkins/1/xyz/original.heic"

    def test_variant_key_always_webp(self) -> None:
        for variant in ("original", "feed", "thumb"):
            key = build_variant_key(
                purpose="place",
                owner_id=5,
                asset_uuid="u",
                variant=variant,  # type: ignore[arg-type]
            )
            assert key == f"places/5/u/{variant}.webp"

    def test_uuid_is_hex_no_dashes(self) -> None:
        uuid = new_asset_uuid()
        assert len(uuid) == 32
        assert "-" not in uuid
        assert all(c in "0123456789abcdef" for c in uuid)


class TestSafeKey:
    @pytest.mark.parametrize(
        "key,expected",
        [
            ("avatars/1/abc/original.jpg", True),
            ("a/b/c/d.webp", True),
            ("../../etc/passwd", False),  # path traversal
            ("avatars/1/abc/../../bad", False),
            ("UPPERCASE/key.jpg", False),  # we lowercase everything
            ("key with spaces.jpg", False),
            ("key;rm -rf.jpg", False),
            ("key?query=1.jpg", False),
            ("", False),
        ],
    )
    def test_is_safe_key(self, key: str, expected: bool) -> None:
        assert is_safe_key(key) is expected


class TestParseFromKey:
    def test_parse_owner_id(self) -> None:
        assert parse_owner_id_from_key("avatars/42/abc/original.jpg") == 42
        assert parse_owner_id_from_key("checkins/1/xyz/feed.webp") == 1

    def test_parse_owner_invalid(self) -> None:
        assert parse_owner_id_from_key("avatars/notanint/abc/x.jpg") is None
        assert parse_owner_id_from_key("too/short") is None
        assert parse_owner_id_from_key("") is None

    def test_known_purpose(self) -> None:
        assert known_purpose_from_key("avatars/1/x/y.jpg") == "avatar"
        assert known_purpose_from_key("checkins/1/x/y.jpg") == "checkin"
        assert known_purpose_from_key("places/1/x/y.jpg") == "place"

    def test_unknown_purpose(self) -> None:
        assert known_purpose_from_key("unknown/1/x/y.jpg") is None
        assert known_purpose_from_key("avatar/1/x/y.jpg") is None  # без 's'