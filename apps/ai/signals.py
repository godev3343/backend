"""
Инвалидация AI-context-кэша.

Любое изменение PlaceVibe / Place меняет контекст промпта, поэтому версию
двигаем атомарно через INCR в Redis. Не пересобираем кэш — он сам
протухнет/пересоберётся при следующем запросе с новой версией в ключе.
"""
from __future__ import annotations

from typing import Any

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.ai.services.context import bump_vibes_version
from apps.places.models import Place, PlaceVibe


@receiver(post_save, sender=PlaceVibe)
@receiver(post_delete, sender=PlaceVibe)
def _invalidate_on_vibe_change(sender: Any, instance: Any, **kwargs: Any) -> None:
    bump_vibes_version()


@receiver(post_save, sender=Place)
@receiver(post_delete, sender=Place)
def _invalidate_on_place_change(sender: Any, instance: Any, **kwargs: Any) -> None:
    # Меняем версию и при правке Place — например, описание изменили,
    # AI-контекст должен это подхватить.
    bump_vibes_version()