"""Кастомный менеджер для User."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import BaseUserManager
from django.db import transaction

if TYPE_CHECKING:
    from apps.users.models import User


class CustomUserManager(BaseUserManager["User"]):
    """
    Менеджер пользователей.

    `create_user` всегда требует email + first_name.
    Пароль опционален (нет = регистрация через Google,
    можно задать позже через set-password флоу).
    """

    use_in_migrations = True

    @transaction.atomic
    def create_user(
        self,
        email: str,
        first_name: str,
        password: str | None = None,
        **extra_fields: Any,
    ) -> "User":
        if not email:
            raise ValueError("Email is required")
        if not first_name:
            raise ValueError("First name is required")

        email = self.normalize_email(email)
        user = self.model(email=email, first_name=first_name, **extra_fields)

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email: str,
        first_name: str = "Admin",
        password: str | None = None,
        **extra_fields: Any,
    ) -> "User":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")
        if not password:
            raise ValueError("Superuser must have a password")

        return self.create_user(
            email=email,
            first_name=first_name,
            password=password,
            **extra_fields,
        )