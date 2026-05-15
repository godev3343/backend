
"""Транзакции поинтов + достижения."""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import CreatedAtModel


class PointsReason(models.TextChoices):
    CHECKIN = "checkin", "Чек-ин"
    FIRST_CHECKIN = "first_checkin", "Первый чек-ин в месте"
    FRIEND_ADDED = "friend_added", "Принята заявка в друзья"
    REVIEW_POSTED = "review_posted", "Опубликован отзыв"


class PointsTransaction(CreatedAtModel):
    """
    История начислений.

    Идемпотентность: повторное событие с тем же (user, reason, ref_type, ref_id)
    не создаст вторую запись — UniqueConstraint выкинет IntegrityError,
    сервис должен ловить и трактовать как «уже начислено».
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="points_transactions",
    )
    delta = models.IntegerField()
    reason = models.CharField(max_length=32, choices=PointsReason.choices)
    ref_type = models.CharField(max_length=32, blank=True, default="")
    ref_id = models.PositiveBigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "gamification_points_tx"
        constraints = [
            models.UniqueConstraint(
                fields=("user", "reason", "ref_type", "ref_id"),
                name="pointstx_idempotency",
                condition=models.Q(ref_id__isnull=False),
            ),
            models.UniqueConstraint(
                fields=("user", "reason"),
                name="pointstx_idempotency_no_ref",
                condition=models.Q(ref_id__isnull=True),
            ),
        ]
        indexes = [
            models.Index(fields=("user", "-created_at"), name="pointstx_user_created_idx"),
        ]

    def __str__(self) -> str:
        return f"u={self.user_id} {self.reason} {self.delta:+d}"


class Achievement(models.Model):
    """
    Определение достижения.

    Загружается из fixtures/achievements.json через seed_achievements.
    Code — стабильный slug, привязан к чекеру в achievements/registry.py.

    Менять threshold/название — через fixture + re-seed. Изменить code —
    значит сделать новую ачивку (старая останется у пользователей, кто
    её получил).
    """

    code = models.CharField(max_length=64, unique=True)
    name_ru = models.CharField(max_length=128)
    description_ru = models.CharField(max_length=512)
    icon_url = models.URLField(blank=True, default="")
    # Порядок отображения в профиле; меньше — раньше.
    order = models.PositiveSmallIntegerField(default=100)

    class Meta:
        db_table = "gamification_achievement"
        ordering = ("order", "id")

    def __str__(self) -> str:
        return f"{self.code} ({self.name_ru})"


class UserAchievement(CreatedAtModel):
    """
    Факт получения ачивки пользователем.

    Одна ачивка получается один раз — UniqueConstraint(user, achievement).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="achievements",
    )
    achievement = models.ForeignKey(
        Achievement,
        on_delete=models.CASCADE,
        related_name="user_achievements",
    )

    class Meta:
        db_table = "gamification_user_achievement"
        constraints = [
            models.UniqueConstraint(
                fields=("user", "achievement"),
                name="userachievement_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=("user", "-created_at"),
                name="userachievement_user_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"u={self.user_id} {self.achievement_id}"