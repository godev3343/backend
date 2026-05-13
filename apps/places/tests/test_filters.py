"""Тесты парсинга query-параметров для list-эндпоинта."""

from __future__ import annotations

import pytest

from apps.places.filters import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    parse_list_query,
)
from apps.places.services.exceptions import (
    BBoxTooLarge,
    InvalidBBox,
    InvalidVibe,
)


class TestParseBBox:
    def test_valid_bbox(self) -> None:
        q = parse_list_query("71.0,51.0,71.5,51.5", None, None, None)
        assert q.bbox.extent == (71.0, 51.0, 71.5, 51.5)

    def test_bbox_rounded_in_key(self) -> None:
        q = parse_list_query("71.123456,51.987654,71.234567,52.098765", None, None, None)
        assert q.bbox_raw_rounded == "71.123,51.988,71.235,52.099"

    def test_missing_bbox(self) -> None:
        with pytest.raises(InvalidBBox):
            parse_list_query(None, None, None, None)

    def test_wrong_part_count(self) -> None:
        with pytest.raises(InvalidBBox):
            parse_list_query("71.0,51.0,71.5", None, None, None)

    def test_non_numeric(self) -> None:
        with pytest.raises(InvalidBBox):
            parse_list_query("a,b,c,d", None, None, None)

    def test_inverted_lng(self) -> None:
        with pytest.raises(InvalidBBox):
            parse_list_query("71.5,51.0,71.0,51.5", None, None, None)

    def test_inverted_lat(self) -> None:
        with pytest.raises(InvalidBBox):
            parse_list_query("71.0,51.5,71.5,51.0", None, None, None)

    def test_out_of_range(self) -> None:
        with pytest.raises(InvalidBBox):
            parse_list_query("-181,-91,181,91", None, None, None)

    def test_too_large(self) -> None:
        # 5° по широте — больше MAX_BBOX_SPAN_DEG (2°)
        with pytest.raises(BBoxTooLarge):
            parse_list_query("70.0,50.0,72.0,55.0", None, None, None)


class TestParseVibes:
    def test_empty(self) -> None:
        q = parse_list_query("71.0,51.0,71.5,51.5", None, None, None)
        assert q.vibes == ()

    def test_single(self) -> None:
        q = parse_list_query("71.0,51.0,71.5,51.5", "calm", None, None)
        assert q.vibes == ("calm",)

    def test_multiple_sorted_deduped(self) -> None:
        q = parse_list_query("71.0,51.0,71.5,51.5", "romantic,calm,calm", None, None)
        assert q.vibes == ("calm", "romantic")

    def test_invalid_tag(self) -> None:
        with pytest.raises(InvalidVibe):
            parse_list_query("71.0,51.0,71.5,51.5", "calm,bogus", None, None)


class TestParseLimit:
    def test_default(self) -> None:
        q = parse_list_query("71.0,51.0,71.5,51.5", None, None, None)
        assert q.limit == DEFAULT_LIMIT

    def test_explicit(self) -> None:
        q = parse_list_query("71.0,51.0,71.5,51.5", None, None, "50")
        assert q.limit == 50

    def test_clamped_to_max(self) -> None:
        q = parse_list_query("71.0,51.0,71.5,51.5", None, None, "9999")
        assert q.limit == MAX_LIMIT

    def test_invalid_falls_back(self) -> None:
        q = parse_list_query("71.0,51.0,71.5,51.5", None, None, "abc")
        assert q.limit == DEFAULT_LIMIT

    def test_negative_falls_back(self) -> None:
        q = parse_list_query("71.0,51.0,71.5,51.5", None, None, "-5")
        assert q.limit == DEFAULT_LIMIT
