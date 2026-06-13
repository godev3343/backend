"""
Локальные фикстуры chat-тестов.

Чистим Django cache (throttle/presence-стейт в Redis) перед каждым тестом,
чтобы серии запросов не упирались в лимиты и presence не протекал между тестами.
"""

from __future__ import annotations

import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _clear_cache():  # type: ignore[no-untyped-def]
    cache.clear()
    yield
    cache.clear()
