"""Кастомный пользователь."""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone

from apps.media.models import MediaAsset
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
    avatar_asset = models.ForeignKey(
        MediaAsset,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    bio = models.CharField(max_length=300, blank=True, default="")

    # preferred_vibes — выбранные на онбординге/в настройках теги вайбов, влияют
    # на ранжирование в AI-промпте. Валидация значений — в сериализаторе,
    # на уровне БД ArrayField не enforces choices.
    preferred_vibes = ArrayField(
        models.CharField(max_length=20),
        size=5,
        default=list,
        blank=True,
    )
    # ai_context — свободный текст "о себе" для AI. До 500 символов.
    # Подмешивается в user-сообщение к модели в /api/ai/recommend.
    ai_context = models.CharField(max_length=500, blank=True, default="")

    # Геймификация
    points = models.PositiveIntegerField(default=0)

    # Email verification (для EPIC 2)
    # Google-юзеры получают timestamp сразу при первом OAuth-логине.
    email_verified_at = models.DateTimeField(null=True, blank=True, db_index=True)

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
    def is_email_verified(self) -> bool:
        return self.email_verified_at is not None

    @property
    def is_onboarded(self) -> bool:
        return self.consent_at is not None and bool(self.display_name)

    @property
    def avatar_url(self) -> str | None:
        """
        Унифицированный публичный URL аватара через MediaAsset.

        Returns None, если аватар не привязан. При обработке (status != PROCESSED)
        MediaAsset.url_feed сам решает что отдать — мы делегируем.

        NB: при чтении из querysets со многими User'ами обязательно
        `.select_related('avatar_asset')`, иначе N+1.
        """
        if self.avatar_asset_id is None:
            return None
        return self.avatar_asset.url_feed
