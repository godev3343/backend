"""AuthService — регистрация, логин, email verification, password reset."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError, transaction
from django.utils.timezone import now

from apps.users.services.dto import TokenPair
from apps.users.services.exceptions import (
    EmailAlreadyExists,
    InvalidCode,
    InvalidCredentials,
    InvalidResetToken,
    UserNotFound,
)
from apps.users.tasks import (
    send_password_reset_email,
    send_verification_email,
)
from apps.users.tokens import (
    consume_email_verify_code,
    consume_password_reset_token,
    generate_email_verify_code,
    generate_password_reset_token,
)

if TYPE_CHECKING:
    from apps.users.models import User as UserType

User = get_user_model()


class AuthService:
    """Stateless — все методы classmethod. Тестируется без mock-DI."""

    @classmethod
    @transaction.atomic
    def register(cls, *, email: str, first_name: str, password: str) -> UserType:
        """
        Создаёт юзера, шлёт код верификации.
        Не возвращает токены — после регистрации нужен явный login.
        """
        email = email.lower().strip()
        try:
            user = User.objects.create_user(  # type: ignore[attr-defined]
                email=email,
                first_name=first_name,
                password=password,
            )
        except IntegrityError as exc:
            raise EmailAlreadyExists() from exc

        cls._send_verification_code(email=email)
        return user

    @classmethod
    def login(cls, *, email: str, password: str) -> TokenPair:
        """
        Email+password логин. Email-верификация НЕ требуется — иначе
        пользователь не сможет дойти до экрана ввода кода.
        Действия, требующие верификации, блокируются permission
        IsEmailVerified.
        """
        user = authenticate(username=email.lower().strip(), password=password)
        if user is None or not user.is_active:
            raise InvalidCredentials()
        return TokenPair.for_user(user)

    # ---------- Email verification -----------------------------------------

    @classmethod
    def request_email_verification(cls, *, email: str) -> None:
        """Идемпотентный 202: тот же ответ для существ./несуществ. email."""
        email = email.lower().strip()
        if User.objects.filter(email=email, is_active=True).exists():
            cls._send_verification_code(email=email)

    @classmethod
    @transaction.atomic
    def confirm_email_verification(cls, *, email: str, code: str) -> UserType:
        email = email.lower().strip()
        if not consume_email_verify_code(email=email, code=code):
            raise InvalidCode()

        try:
            user = User.objects.select_for_update().get(email=email, is_active=True)
        except User.DoesNotExist as exc:
            raise UserNotFound() from exc

        if user.email_verified_at is None:
            user.email_verified_at = now()
            user.save(update_fields=["email_verified_at"])
        return user

    # ---------- Password reset ---------------------------------------------

    @classmethod
    def request_password_reset(cls, *, email: str) -> None:
        """Идемпотентно — не палим существование email."""
        email = email.lower().strip()
        try:
            user = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            return

        token = generate_password_reset_token(user_id=user.pk)
        send_password_reset_email.delay(email=email, token=token)

    @classmethod
    @transaction.atomic
    def confirm_password_reset(cls, *, token: str, new_password: str) -> UserType:
        user_id = consume_password_reset_token(token=token)
        if user_id is None:
            raise InvalidResetToken()

        try:
            user = User.objects.select_for_update().get(pk=user_id, is_active=True)
        except User.DoesNotExist as exc:
            raise InvalidResetToken() from exc

        user.set_password(new_password)
        user.save(update_fields=["password"])
        return user

    # ---------- internals --------------------------------------------------

    @classmethod
    def _send_verification_code(cls, *, email: str) -> None:
        code = generate_email_verify_code(email=email)
        send_verification_email.delay(email=email, code=code.code)
