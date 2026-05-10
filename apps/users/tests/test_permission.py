"""Тесты IsEmailVerified и IsOnboarded permissions.

Стратегия: не используем URLPatternsTestCase (он на SimpleTestCase,
без БД). Вместо этого — тестируем permission-классы напрямую через
их has_permission(), мокая request.user.

Это даже лучше: не зависим от роутинга/middleware/throttling.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.utils.timezone import now

from apps.users.permissions import IsEmailVerified, IsOnboarded
from apps.users.tests.factories import UserFactory


def _fake_request(user):  # type: ignore[no-untyped-def]
    """Мок request с нужным user. Permission смотрит только на .user."""
    return SimpleNamespace(user=user)


class TestIsEmailVerified:
    """Permission проверяется напрямую, без HTTP-слоя."""

    def test_anonymous_blocked(self) -> None:
        anon = SimpleNamespace(is_authenticated=False)
        assert IsEmailVerified().has_permission(_fake_request(anon), view=None) is False  # type: ignore[arg-type]

    @pytest.mark.django_db
    def test_unverified_user_blocked(self) -> None:
        user = UserFactory(email_verified_at=None)
        assert IsEmailVerified().has_permission(_fake_request(user), view=None) is False  # type: ignore[arg-type]

    @pytest.mark.django_db
    def test_verified_user_allowed(self) -> None:
        user = UserFactory(email_verified_at=now())
        assert IsEmailVerified().has_permission(_fake_request(user), view=None) is True  # type: ignore[arg-type]


class TestIsOnboarded:
    def test_anonymous_blocked(self) -> None:
        anon = SimpleNamespace(is_authenticated=False)
        assert IsOnboarded().has_permission(_fake_request(anon), view=None) is False  # type: ignore[arg-type]

    @pytest.mark.django_db
    def test_not_onboarded_blocked(self) -> None:
        user = UserFactory(display_name="", consent_at=None)
        assert IsOnboarded().has_permission(_fake_request(user), view=None) is False  # type: ignore[arg-type]

    @pytest.mark.django_db
    def test_partially_onboarded_blocked(self) -> None:
        # display_name есть, consent_at нет
        user = UserFactory(display_name="alice", consent_at=None)
        assert IsOnboarded().has_permission(_fake_request(user), view=None) is False  # type: ignore[arg-type]

    @pytest.mark.django_db
    def test_onboarded_allowed(self) -> None:
        user = UserFactory(display_name="alice", consent_at=now())
        assert IsOnboarded().has_permission(_fake_request(user), view=None) is True  # type: ignore[arg-type]