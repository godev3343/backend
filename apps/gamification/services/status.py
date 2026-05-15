"""
Это property поверх User.points, не отдельная сущность.
Пороги — детали представления.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class Status:
    """Статус пользователя для отображения в профиле."""

    code: str
    name_ru: str
    threshold: int


_STATUSES: Final[tuple[Status, ...]] = (
    Status(code="legend", name_ru="Легенда города", threshold=10_000),
    Status(code="insider", name_ru="Инсайдер", threshold=2_000),
    Status(code="navigator", name_ru="Навигатор города", threshold=500),
    Status(code="explorer", name_ru="Исследователь", threshold=100),
    Status(code="guest", name_ru="Гость города", threshold=0),
)


def get_status_for_points(points: int) -> Status:
    """
    Возвращает текущий статус для указанного количества поинтов.

    Поинты могут быть отрицательными (теоретически — в pre-MVP это не
    случается, но защищаемся): тогда отдаём guest.
    """
    for status in _STATUSES:
        if points >= status.threshold:
            return status
    return _STATUSES[-1]  # guest


def all_statuses() -> tuple[Status, ...]:
    """Все статусы по возрастанию порога — для UI «как получить следующий»."""
    return tuple(reversed(_STATUSES))