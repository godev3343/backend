"""Кастомный пользователь."""
from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.users.managers import CustomUserManager


class User(AbstractBaseUser, PermissionsMixin):
    """
    Идентификация — email (всегда есть).
    Опционально: phone (SMS-логин позже), google_sub (Google OAuth).

    Пароль опциональный — если юзер зашёл только через Google,
    пароля нет (set_unusable_password). Чтобы залогиниться email+pass,
    нужно сначала задать пароль (флоу "set password").
    """

    # Identifier
    email = models.EmailField(unique=True, db_index=True)

    # Опциональные внешние identifier'ы
    phone = models.CharField(
        max_length=32,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
    )
    google_sub = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
    )

    # Личное имя
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True, default="")

    # Профиль (публичная часть)
    display_name = models.CharField(max_length=100, blank=True, default="")
    avatar_url = models.URLField(blank=True, default="")
    bio = models.CharField(max_length=300, blank=True, default="")

    # Геймификация
    points = models.PositiveIntegerField(default=0)

    # Системное
    consent_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = CustomUserManager()  # type: ignore[assignment,misc]

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = ["first_name"]  # для createsuperuser

    class Meta:
        db_table = "users_user"
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self) -> str:
        return self.display_name or self.first_name or self.email

    @property
    def full_name(self) -> str:
        """Имя + фамилия одной строкой."""
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def public_name(self) -> str:
        """Что показываем другим юзерам — display_name если есть, иначе first_name."""
        return self.display_name or self.first_name

    @property
    def is_onboarded(self) -> bool:
        return self.consent_at is not None and bool(self.display_name)