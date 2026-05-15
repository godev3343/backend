"""Тесты статусов пользователей."""
from __future__ import annotations

import pytest

from apps.gamification.services.status import (
    all_statuses,
    get_status_for_points,
)


class TestStatusBoundaries:
    @pytest.mark.parametrize(
        ("points", "expected_code"),
        [
            (0, "guest"),
            (1, "guest"),
            (99, "guest"),
            (100, "explorer"),
            (499, "explorer"),
            (500, "navigator"),
            (1999, "navigator"),
            (2000, "insider"),
            (9999, "insider"),
            (10_000, "legend"),
            (1_000_000, "legend"),
        ],
    )
    def test_boundaries(self, points: int, expected_code: str) -> None:
        assert get_status_for_points(points).code == expected_code

    def test_negative_points_fall_back_to_guest(self) -> None:
        # Защита от рассинхрона — теоретически возможна отрицательная сумма
        assert get_status_for_points(-1).code == "guest"

    def test_all_statuses_sorted_ascending(self) -> None:
        statuses = all_statuses()
        thresholds = [s.threshold for s in statuses]
        assert thresholds == sorted(thresholds)