"""Дружба между пользователями."""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import CreatedAtModel


class FriendshipStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACCEPTED = "accepted", "Accepted"
    BLOCKED = "blocked", "Blocked"


class Friendship(CreatedAtModel):
    """
    Направленная заявка/дружба.

    Дизайн-решение: одна запись с направлением from_user → to_user.
    На accept меняем status, не создаём зеркальную запись.
    Проверка `is_friends(a, b)` — Q(from=a, to=b) | Q(from=b, to=a) с status=accepted.
    """

    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="friendships_sent",
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="friendships_received",
    )
    status = models.CharField(
        max_length=16,
        choices=FriendshipStatus.choices,
        default=FriendshipStatus.PENDING,
        db_index=True,
    )

    class Meta:
        db_table = "social_friendship"
        constraints = [
            models.UniqueConstraint(
                fields=("from_user", "to_user"),
                name="friendship_unique_pair",
            ),
            models.CheckConstraint(
                condition=~models.Q(from_user=models.F("to_user")),
                name="friendship_no_self",
            ),
        ]
        indexes = [
            models.Index(fields=("to_user", "status"), name="friendship_to_status_idx"),
            models.Index(fields=("from_user", "status"), name="friendship_from_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.from_user_id} → {self.to_user_id} [{self.status}]"