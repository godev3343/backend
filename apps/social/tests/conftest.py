"""
Локальные фикстуры для social-тестов.

Throttle-state хранится в Django cache (Redis). Чистим перед каждым
тестом, иначе серия запросов на friend_request упирается в 30/h лимит.
"""
from __future__ import annotations

import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _clear_cache():  # type: ignore[no-untyped-def]
    cache.clear()
    yield
    cache.clear()