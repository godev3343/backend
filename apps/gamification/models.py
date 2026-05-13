"""Транзакции поинтов с идемпотентностью."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import CreatedAtModel


class PointsReason(models.TextChoices):
    CHECKIN = "checkin", "Checkin"
    FIRST_CHECKIN = "first_checkin", "First check-in at place"
    FRIEND_ADDED = "friend_added", "Friend added"


class PointsTransaction(CreatedAtModel):
    """
    История начислений.

    Идемпотентность: повторное событие с тем же (user, reason, ref_type, ref_id)
    не создаст вторую запись — UniqueConstraint выкинет IntegrityError,
    сервис должен ловить и трактовать как «уже начислено».

    ref_type/ref_id — без GenericFK, чтобы не таскать ContentType
    (нам обратные запросы не нужны, нужна только уникальность).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="points_transactions",
    )
    delta = models.IntegerField()
    reason = models.CharField(max_length=32, choices=PointsReason.choices)
    ref_type = models.CharField(max_length=64, blank=True, default="")
    ref_id = models.PositiveBigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "gamification_points_tx"
        constraints = [
            models.UniqueConstraint(
                fields=("user", "reason", "ref_type", "ref_id"),
                name="pointstx_idempotency",
                # Если ref_id NULL — уникальность по (user, reason) без ref
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
