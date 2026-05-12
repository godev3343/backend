from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils.timezone import now

from apps.events.filters import DEFAULT_LIMIT, DEFAULT_PERIOD_DAYS, parse_list_query
from apps.events.services.exceptions import (
    EventsBBoxTooLarge,
    EventsInvalidBBox,
    InvalidPeriod,
)


class TestParsePeriod:
    def test_defaults(self) -> None:
        q = parse_list_query(None, None, None, None)
        # from ≈ now, to ≈ from + 14d. Допуск 5 секунд от текущего времени.
        assert abs((q.from_ - now()).total_seconds()) < 5
        assert abs((q.to - q.from_ - timedelta(days=DEFAULT_PERIOD_DAYS)).total_seconds()) < 1

    def test_explicit_from_to(self) -> None:
        from_ = "2026-06-01T00:00:00+00:00"
        to = "2026-06-15T00:00:00+00:00"
        q = parse_list_query(from_, to, None, None)
        assert q.from_.isoformat() == "2026-06-01T00:00:00+00:00"
        assert q.to.isoformat() == "2026-06-15T00:00:00+00:00"

    def test_only_from_extends_to_default(self) -> None:
        from_ = "2026-06-01T00:00:00+00:00"
        q = parse_list_query(from_, None, None, None)
        assert q.to == q.from_ + timedelta(days=DEFAULT_PERIOD_DAYS)

    def test_from_must_have_tz(self) -> None:
        with pytest.raises(InvalidPeriod):
            parse_list_query("2026-06-01T00:00:00", None, None, None)

    def test_from_invalid_format(self) -> None:
        with pytest.raises(InvalidPeriod):
            parse_list_query("not-a-date", None, None, None)

    def test_to_before_from(self) -> None:
        with pytest.raises(InvalidPeriod):
            parse_list_query(
                "2026-06-15T00:00:00+00:00",
                "2026-06-01T00:00:00+00:00",
                None,
                None,
            )

    def test_to_equals_from(self) -> None:
        with pytest.raises(InvalidPeriod):
            parse_list_query(
                "2026-06-01T00:00:00+00:00",
                "2026-06-01T00:00:00+00:00",
                None,
                None,
            )


class TestParseBBox:
    def test_none_means_no_filter(self) -> None:
        q = parse_list_query(None, None, None, None)
        assert q.bbox is None

    def test_valid_bbox(self) -> None:
        q = parse_list_query(None, None, "71.0,51.0,71.5,51.5", None)
        assert q.bbox is not None
        assert q.bbox.extent == (71.0, 51.0, 71.5, 51.5)

    def test_invalid_format(self) -> None:
        with pytest.raises(EventsInvalidBBox):
            parse_list_query(None, None, "71.0,51.0,71.5", None)

    def test_inverted(self) -> None:
        with pytest.raises(EventsInvalidBBox):
            parse_list_query(None, None, "71.5,51.0,71.0,51.5", None)

    def test_too_large(self) -> None:
        with pytest.raises(EventsBBoxTooLarge):
            parse_list_query(None, None, "70.0,50.0,73.0,53.0", None)


class TestParseLimit:
    def test_default(self) -> None:
        q = parse_list_query(None, None, None, None)
        assert q.limit == DEFAULT_LIMIT

    def test_explicit(self) -> None:
        q = parse_list_query(None, None, None, "10")
        assert q.limit == 10

    def test_capped_at_max(self) -> None:
        q = parse_list_query(None, None, None, "9999")
        assert q.limit == 200  # MAX_LIMIT

    def test_invalid_falls_back_to_default(self) -> None:
        q = parse_list_query(None, None, None, "not-a-number")
        assert q.limit == DEFAULT_LIMIT