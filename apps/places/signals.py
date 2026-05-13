"""
Инвалидация кэша списка мест.

Любое изменение Place / PlaceVibe / PlacePhoto инвалидирует ВЕСЬ список
маркеров через bump_version() — это копеечная операция (INCR в Redis),
которая делает все ранее сохранённые ключи кэша неактуальными.

Геометрия места (location) — самое частое поле, которое забывают. На save
мы не отличаем "сменили name" от "перенесли координаты"; проще инвалидировать всегда.
"""

from __future__ import annotations

from typing import Any

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.places.models import Place, PlacePhoto, PlaceVibe
from apps.places.services.cache import bump_version


@receiver(post_save, sender=Place)
@receiver(post_delete, sender=Place)
def _invalidate_on_place_change(sender: Any, instance: Any, **kwargs: Any) -> None:
    bump_version()


@receiver(post_save, sender=PlaceVibe)
@receiver(post_delete, sender=PlaceVibe)
def _invalidate_on_vibe_change(sender: Any, instance: Any, **kwargs: Any) -> None:
    bump_version()


@receiver(post_save, sender=PlacePhoto)
@receiver(post_delete, sender=PlacePhoto)
def _invalidate_on_photo_change(sender: Any, instance: Any, **kwargs: Any) -> None:
    bump_version()
