from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils.timezone import now

from apps.users.tests.factories import UserFactory

User = get_user_model()


@pytest.mark.django_db
class TestUserModel:
    def test_create_minimal(self) -> None:
        user = UserFactory()
        assert user.pk
        assert user.email
        assert user.first_name

    def test_email_unique(self) -> None:
        User.objects.create_user(email="dup@test.local", first_name="A")
        with pytest.raises(IntegrityError):
            User.objects.create_user(email="dup@test.local", first_name="B")

    def test_phone_unique_when_set(self) -> None:
        UserFactory(phone="+77001111111")
        with pytest.raises(IntegrityError):
            UserFactory(phone="+77001111111")

    def test_phone_nullable(self) -> None:
        u1 = UserFactory(phone=None)
        u2 = UserFactory(phone=None)
        assert u1.phone is None and u2.phone is None  # обе nullable, no conflict

    def test_full_name(self) -> None:
        u = UserFactory(first_name="Иван", last_name="Петров")
        assert u.full_name == "Иван Петров"

    def test_full_name_no_last(self) -> None:
        u = UserFactory(first_name="Иван", last_name="")
        assert u.full_name == "Иван"

    def test_public_name_fallback(self) -> None:
        u = UserFactory(first_name="Иван", display_name="")
        assert u.public_name == "Иван"

    def test_public_name_display(self) -> None:
        u = UserFactory(first_name="Иван", display_name="vanya_kz")
        assert u.public_name == "vanya_kz"

    def test_is_onboarded(self) -> None:
        u = UserFactory(display_name="", consent_at=None)
        assert not u.is_onboarded
        u.display_name = "test"
        u.consent_at = now()
        assert u.is_onboarded


@pytest.mark.django_db
class TestCustomUserManager:
    def test_create_user_no_password(self) -> None:
        u = User.objects.create_user(email="x@test.local", first_name="X")
        assert not u.has_usable_password()

    def test_create_user_with_password(self) -> None:
        u = User.objects.create_user(
            email="x@test.local", first_name="X", password="strongpass123"
        )
        assert u.has_usable_password()
        assert u.check_password("strongpass123")

    def test_create_user_requires_email(self) -> None:
        with pytest.raises(ValueError, match="Email"):
            User.objects.create_user(email="", first_name="X")

    def test_create_user_requires_first_name(self) -> None:
        with pytest.raises(ValueError, match="First name"):
            User.objects.create_user(email="x@test.local", first_name="")

    def test_create_superuser(self) -> None:
        u = User.objects.create_superuser(
            email="admin@test.local", password="strongpass123"
        )
        assert u.is_superuser and u.is_staff

    def test_create_superuser_requires_password(self) -> None:
        with pytest.raises(ValueError, match="password"):
            User.objects.create_superuser(email="admin@test.local")