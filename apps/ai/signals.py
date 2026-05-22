"""
Инвалидация AI-context-кэша. Никогда не роняет save/delete.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.ai.services.context import bump_vibes_version
from apps.places.models import Place, PlaceVibe

logger = logging.getLogger(__name__)


def _safe_bump_vibes() -> None:
    try:
        bump_vibes_version()
    except Exception:
        logger.warning("bump_vibes_version failed", exc_info=True)


@receiver(post_save, sender=PlaceVibe)
@receiver(post_delete, sender=PlaceVibe)
def _invalidate_on_vibe_change(sender: Any, instance: Any, **kwargs: Any) -> None:
    _safe_bump_vibes()


@receiver(post_save, sender=Place)
@receiver(post_delete, sender=Place)
def _invalidate_on_place_change(sender: Any, instance: Any, **kwargs: Any) -> None:
    _safe_bump_vibes()