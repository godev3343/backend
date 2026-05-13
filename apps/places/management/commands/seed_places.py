"""
Seed Place + PlaceCategory + PlaceVibe из JSON-фикстуры.

Идемпотентно: update_or_create по name, вайбы пересоздаются.
Если в фикстуре есть поле "city" — используется оно; иначе значение из
параметра --city (default 'astana'). Полезно когда одна фикстура содержит
данные одного города — поле city указано один раз в meta-блоке.

Пример вызова:
    python manage.py seed_places --file fixtures/places_astana.json
    python manage.py seed_places --file fixtures/places.json --city astana
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction

from apps.places.models import City, Place, PlaceCategory, PlaceVibe


class Command(BaseCommand):
    help = "Seed places + vibes from JSON fixture (idempotent)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--file",
            type=str,
            default="fixtures/places_astana.json",
            help="Путь к JSON-фикстуре относительно BASE_DIR",
        )
        parser.add_argument(
            "--city",
            type=str,
            default=City.ASTANA.value,
            choices=[c.value for c in City],
            help="Город по умолчанию (если в фикстуре нет meta.city и в записи нет city)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Удалить все Place перед сидом (для dev)",
        )

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        path = Path(settings.BASE_DIR) / options["file"]
        if not path.exists():
            self.stderr.write(self.style.ERROR(f"Не найден файл {path}"))
            return

        if options["clear"]:
            deleted, _ = Place.objects.all().delete()
            self.stdout.write(f"Удалено мест: {deleted}")

        data = json.loads(path.read_text(encoding="utf-8"))

        # Город по приоритету: meta.city > --city параметр
        default_city: str = data.get("meta", {}).get("city") or options["city"]

        # Категории
        categories: dict[str, PlaceCategory] = {}
        for cat in data.get("categories", []):
            obj, _ = PlaceCategory.objects.get_or_create(
                slug=cat["slug"],
                defaults={
                    "name_ru": cat["name_ru"],
                    "name_kk": cat.get("name_kk", ""),
                },
            )
            categories[cat["slug"]] = obj

        # Места
        created = 0
        updated = 0
        for item in data.get("places", []):
            cat = categories.get(item["category_slug"])
            if cat is None:
                self.stderr.write(f"Пропущена категория: {item['category_slug']}")
                continue

            city = item.get("city", default_city)

            place, was_created = Place.objects.update_or_create(
                name=item["name"],
                defaults={
                    "category": cat,
                    "city": city,
                    "location": Point(item["lng"], item["lat"], srid=4326),
                    "address": item.get("address", ""),
                    "phone": item.get("phone", ""),
                    "hours_json": item.get("hours", {}),
                    "description": item.get("description", ""),
                    "is_verified": item.get("is_verified", True),
                },
            )

            # Вайбы — пересоздаём, чтобы сидинг был идемпотентен
            PlaceVibe.objects.filter(place=place).delete()
            for vibe in item.get("vibes", []):
                PlaceVibe.objects.create(
                    place=place,
                    tag=vibe["tag"],
                    weight=vibe["weight"],
                )

            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"Готово. Создано: {created}, обновлено: {updated}"))
