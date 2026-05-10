"""Тесты на email_verified_at и is_email_verified property."""
from __future__ import annotations

import pytest
from django.utils.timezone import now

from apps.users.tests.factories import UserFactory


@pytest.mark.django_db
class TestEmailVerification:
    def test_unverified_by_default(self) -> None:
        u = UserFactory()
        assert u.email_verified_at is None
        assert u.is_email_verified is False

    def test_verified_when_timestamp_set(self) -> None:
        u = UserFactory(email_verified_at=now())
        assert u.is_email_verified is True
