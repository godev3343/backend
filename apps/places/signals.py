"""
Инвалидация кэша списка мест.

Любое изменение Place / PlaceVibe / PlacePhoto инвалидирует ВЕСЬ список
маркеров через bump_version() — это копеечная операция (INCR в Redis).

Сигналы НИКОГДА не должны ронять save/delete — кэш best-effort.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.places.models import Place, PlacePhoto, PlaceVibe
from apps.places.services.cache import bump_version

logger = logging.getLogger(__name__)


def _safe_bump(sender_name: str, instance_pk: Any) -> None:
    try:
        bump_version()
    except Exception:
        logger.warning(
            "bump_version failed for %s pk=%s", sender_name, instance_pk, exc_info=True
        )


@receiver(post_save, sender=Place)
@receiver(post_delete, sender=Place)
def _invalidate_on_place_change(sender: Any, instance: Any, **kwargs: Any) -> None:
    _safe_bump("Place", getattr(instance, "pk", None))


@receiver(post_save, sender=PlaceVibe)
@receiver(post_delete, sender=PlaceVibe)
def _invalidate_on_vibe_change(sender: Any, instance: Any, **kwargs: Any) -> None:
    _safe_bump("PlaceVibe", getattr(instance, "pk", None))


@receiver(post_save, sender=PlacePhoto)
@receiver(post_delete, sender=PlacePhoto)
def _invalidate_on_photo_change(sender: Any, instance: Any, **kwargs: Any) -> None:
    _safe_bump("PlacePhoto", getattr(instance, "pk", None))