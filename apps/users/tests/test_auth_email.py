# apps/users/tests/test_auth_email.py
"""Тесты email/password флоу: register, login, refresh, logout, verify, reset."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.mark.django_db
class TestRegister:
    def test_register_success(self, client: APIClient) -> None:
        url = reverse("users:register")
        resp = client.post(
            url,
            {
                "email": "new@test.local",
                "first_name": "Иван",
                "password": "strong-pass-123",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        user = User.objects.get(email="new@test.local")
        assert user.first_name == "Иван"
        assert user.has_usable_password()
        assert user.email_verified_at is None
        # Письмо ушло (EAGER в test settings)
        assert len(mail.outbox) == 1
        assert "new@test.local" in mail.outbox[0].to

    def test_register_duplicate_email(self, client: APIClient) -> None:
        User.objects.create_user(email="dup@test.local", first_name="A", password="pass-12345")
        url = reverse("users:register")
        resp = client.post(
            url,
            {
                "email": "dup@test.local",
                "first_name": "B",
                "password": "strong-pass-123",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_409_CONFLICT

    def test_register_weak_password(self, client: APIClient) -> None:
        url = reverse("users:register")
        resp = client.post(
            url,
            {"email": "weak@test.local", "first_name": "X", "password": "123"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_email_normalized(self, client: APIClient) -> None:
        url = reverse("users:register")
        client.post(
            url,
            {
                "email": "  MIXED@Test.Local  ",
                "first_name": "X",
                "password": "strong-pass-123",
            },
            format="json",
        )
        assert User.objects.filter(email="mixed@test.local").exists()


@pytest.mark.django_db
class TestLogin:
    def test_login_success(self, client: APIClient) -> None:
        User.objects.create_user(email="login@test.local", first_name="X", password="pass-12345")
        url = reverse("users:login")
        resp = client.post(
            url,
            {"email": "login@test.local", "password": "pass-12345"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert "access" in resp.json()
        assert "refresh" in resp.json()

    def test_login_wrong_password(self, client: APIClient) -> None:
        User.objects.create_user(email="login@test.local", first_name="X", password="pass-12345")
        url = reverse("users:login")
        resp = client.post(
            url,
            {"email": "login@test.local", "password": "wrong-pass-456"},
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_inactive_user(self, client: APIClient) -> None:
        user = User.objects.create_user(
            email="login@test.local", first_name="X", password="pass-12345"
        )
        user.is_active = False
        user.save()
        url = reverse("users:login")
        resp = client.post(
            url,
            {"email": "login@test.local", "password": "pass-12345"},
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestRefreshAndLogout:
    def _login(self, client: APIClient) -> dict:
        User.objects.create_user(email="rt@test.local", first_name="X", password="pass-12345")
        resp = client.post(
            reverse("users:login"),
            {"email": "rt@test.local", "password": "pass-12345"},
            format="json",
        )
        return resp.json()

    def test_refresh_rotates_token(self, client: APIClient) -> None:
        tokens = self._login(client)
        resp = client.post(
            reverse("users:refresh"),
            {"refresh": tokens["refresh"]},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        new_tokens = resp.json()
        assert "refresh" in new_tokens
        assert new_tokens["refresh"] != tokens["refresh"]

    def test_old_refresh_blacklisted_after_rotation(self, client: APIClient) -> None:
        tokens = self._login(client)
        client.post(
            reverse("users:refresh"),
            {"refresh": tokens["refresh"]},
            format="json",
        )
        resp = client.post(
            reverse("users:refresh"),
            {"refresh": tokens["refresh"]},
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_blacklists_refresh(self, client: APIClient) -> None:
        tokens = self._login(client)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        resp = client.post(
            reverse("users:logout"),
            {"refresh": tokens["refresh"]},
            format="json",
        )
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        # После logout refresh не работает
        client.credentials()
        resp = client.post(
            reverse("users:refresh"),
            {"refresh": tokens["refresh"]},
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestEmailVerification:
    def test_request_unknown_email_returns_202(self, client: APIClient) -> None:
        """User-enumeration защита: одинаковый ответ для существ./несуществ."""
        resp = client.post(
            reverse("users:email_verify_request"),
            {"email": "nobody@test.local"},
            format="json",
        )
        assert resp.status_code == status.HTTP_202_ACCEPTED
        assert len(mail.outbox) == 0

    def test_request_known_email_sends_code(self, client: APIClient) -> None:
        User.objects.create_user(email="v@test.local", first_name="X", password="pass-12345")
        resp = client.post(
            reverse("users:email_verify_request"),
            {"email": "v@test.local"},
            format="json",
        )
        assert resp.status_code == status.HTTP_202_ACCEPTED
        assert len(mail.outbox) == 1

    def test_confirm_with_valid_code(self, client: APIClient) -> None:
        User.objects.create_user(email="v@test.local", first_name="X", password="pass-12345")
        client.post(
            reverse("users:email_verify_request"),
            {"email": "v@test.local"},
            format="json",
        )
        # Извлекаем код из текста письма
        body = mail.outbox[0].body
        code = next(line.split(": ")[1].strip() for line in body.splitlines() if "Ваш код" in line)

        resp = client.post(
            reverse("users:email_verify_confirm"),
            {"email": "v@test.local", "code": code},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        user = User.objects.get(email="v@test.local")
        assert user.is_email_verified

    def test_confirm_with_wrong_code(self, client: APIClient) -> None:
        User.objects.create_user(email="v@test.local", first_name="X", password="pass-12345")
        client.post(
            reverse("users:email_verify_request"),
            {"email": "v@test.local"},
            format="json",
        )
        resp = client.post(
            reverse("users:email_verify_confirm"),
            {"email": "v@test.local", "code": "000000"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_code_consumed_after_use(self, client: APIClient) -> None:
        User.objects.create_user(email="v@test.local", first_name="X", password="pass-12345")
        client.post(
            reverse("users:email_verify_request"),
            {"email": "v@test.local"},
            format="json",
        )
        body = mail.outbox[0].body
        code = next(line.split(": ")[1].strip() for line in body.splitlines() if "Ваш код" in line)

        client.post(
            reverse("users:email_verify_confirm"),
            {"email": "v@test.local", "code": code},
            format="json",
        )
        # Повторно — невалиден
        resp = client.post(
            reverse("users:email_verify_confirm"),
            {"email": "v@test.local", "code": code},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestPasswordReset:
    def test_request_unknown_email_returns_202(self, client: APIClient) -> None:
        resp = client.post(
            reverse("users:password_reset_request"),
            {"email": "nobody@test.local"},
            format="json",
        )
        assert resp.status_code == status.HTTP_202_ACCEPTED
        assert len(mail.outbox) == 0

    def test_request_and_confirm(self, client: APIClient) -> None:
        User.objects.create_user(email="r@test.local", first_name="X", password="old-pass-1234")
        client.post(
            reverse("users:password_reset_request"),
            {"email": "r@test.local"},
            format="json",
        )
        assert len(mail.outbox) == 1
        body = mail.outbox[0].body
        token = body.split("token=")[1].split()[0].strip()

        resp = client.post(
            reverse("users:password_reset_confirm"),
            {"token": token, "new_password": "new-strong-pass-1234"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK

        # Старый пароль не работает
        resp = client.post(
            reverse("users:login"),
            {"email": "r@test.local", "password": "old-pass-1234"},
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

        # Новый работает
        resp = client.post(
            reverse("users:login"),
            {"email": "r@test.local", "password": "new-strong-pass-1234"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_confirm_invalid_token(self, client: APIClient) -> None:
        resp = client.post(
            reverse("users:password_reset_confirm"),
            {"token": "totally-bogus", "new_password": "new-strong-pass-1234"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_token_consumed_after_use(self, client: APIClient) -> None:
        User.objects.create_user(email="r@test.local", first_name="X", password="old-pass-1234")
        client.post(
            reverse("users:password_reset_request"),
            {"email": "r@test.local"},
            format="json",
        )
        body = mail.outbox[0].body
        token = body.split("token=")[1].split()[0].strip()

        client.post(
            reverse("users:password_reset_confirm"),
            {"token": token, "new_password": "new-strong-pass-1234"},
            format="json",
        )
        # Повторно — невалиден
        resp = client.post(
            reverse("users:password_reset_confirm"),
            {"token": token, "new_password": "other-pass-1234"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
