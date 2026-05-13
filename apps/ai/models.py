"""
Логи запросов к LLM — для дебага, контроля затрат и аудита.

Храним только summary, не полные ответы и не контекст-блоки —
иначе таблица разрастётся, а PII (query пользователя) и так уже там.
"""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models


class AiRequestStatus(models.TextChoices):
    OK = "ok", "OK"
    ERROR = "error", "Error"


class AiRequestLog(models.Model):
    """
    Запись на каждый POST /api/ai/recommend.

    response_summary — компактный JSON с id и краткими reasoning,
    не полный текст модели. На случай разбора жалоб "AI порекомендовал
    чушь" — этого хватит.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_request_logs",
    )
    query = models.CharField(max_length=500)
    response_summary = models.JSONField(default=list, blank=True)

    # Usage / стоимость
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    cached_input_tokens = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField(
        max_digits=10, decimal_places=6, default=Decimal("0")
    )

    # Технические метаданные
    model = models.CharField(max_length=64)
    latency_ms = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=10,
        choices=AiRequestStatus.choices,
        default=AiRequestStatus.OK,
    )
    error = models.CharField(max_length=500, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "ai_request_log"
        indexes = [
            models.Index(
                fields=("user", "-created_at"), name="ailog_user_created_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"ailog#{self.pk} u={self.user_id} {self.status}"