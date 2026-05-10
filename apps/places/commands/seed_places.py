"""Сидинг 50+ заведений Астаны из JSON-фикстуры."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.places.models import Place, PlaceCategory, PlaceVibe


class Command(BaseCommand):
    help = "Сидит места и вайбы из fixtures/places.json"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--file",
            type=str,
            default="fixtures/places.json",
            help="Путь к JSON-фикстуре относительно BASE_DIR",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Удалить все Place перед сидом (для dev)",
        )

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        from django.conf import settings

        path = Path(settings.BASE_DIR) / options["file"]
        if not path.exists():
            self.stderr.write(self.style.ERROR(f"Не найден файл {path}"))
            return

        if options["clear"]:
            deleted, _ = Place.objects.all().delete()
            self.stdout.write(f"Удалено мест: {deleted}")

        data = json.loads(path.read_text(encoding="utf-8"))

        # Категории
        categories: dict[str, PlaceCategory] = {}
        for cat in data.get("categories", []):
            obj, _ = PlaceCategory.objects.get_or_create(
                slug=cat["slug"],
                defaults={"name_ru": cat["name_ru"], "name_kk": cat.get("name_kk", "")},
            )
            categories[cat["slug"]] = obj

        # Места
        created = 0
        for item in data.get("places", []):
            cat = categories.get(item["category_slug"])
            if cat is None:
                self.stderr.write(f"Пропущена категория: {item['category_slug']}")
                continue

            place, was_created = Place.objects.update_or_create(
                name=item["name"],
                defaults={
                    "category": cat,
                    "location": Point(item["lng"], item["lat"], srid=4326),
                    "address": item.get("address", ""),
                    "phone": item.get("phone", ""),
                    "hours_json": item.get("hours", {}),
                    "description": item.get("description", ""),
                    "is_verified": item.get("is_verified", True),
                },
            )

            # Вайбы
            PlaceVibe.objects.filter(place=place).delete()
            for vibe in item.get("vibes", []):
                PlaceVibe.objects.create(
                    place=place,
                    tag=vibe["tag"],
                    weight=vibe["weight"],
                )

            if was_created:
                created += 1

        self.stdout.write(self.style.SUCCESS(f"Готово. Новых: {created}, всего обработано: {len(data.get('places', []))}"))