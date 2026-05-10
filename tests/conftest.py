"""Глобальные фикстуры pytest.

user_factory / authed_client появятся после Epic 1.1
(когда будет apps/users/tests/factories.py).
"""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()