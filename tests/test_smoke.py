"""Smoke-тесты — приложение поднимается, health работает."""

from __future__ import annotations

import pytest
from rest_framework import status


@pytest.mark.django_db
def test_health_endpoint(api_client) -> None:
    response = api_client.get("/health/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_readiness_endpoint(api_client) -> None:
    response = api_client.get("/ready/")
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["redis"] == "ok"
