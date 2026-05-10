"""
Локальные фикстуры для auth-тестов.

Throttle-state хранится в Django cache (Redis). Между тестами он не
сбрасывается автоматически, и серия тестов вида register → register
→ register упирается в 5/min лимит уже на 6-м запросе.

Чистим cache перед каждым тестом.
"""
from __future__ import annotations

import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _clear_cache():  # type: ignore[no-untyped-def]
    """Сбрасывает Redis-cache перед и после каждого теста."""
    cache.clear()
    yield
    cache.clear()