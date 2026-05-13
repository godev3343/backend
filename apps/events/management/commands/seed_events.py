"""Сидинг 10+ событий из JSON-фикстуры."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from django.utils.timezone import make_aware

from apps.events.models import Event
from apps.places.models import Place


class Command(BaseCommand):
    help = "Сидит события из fixtures/events.json"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--file", type=str, default="fixtures/events.json")
        parser.add_argument("--clear", action="store_true")

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        path = Path(settings.BASE_DIR) / options["file"]
        if not path.exists():
            self.stderr.write(self.style.ERROR(f"Не найден файл {path}"))
            return

        if options["clear"]:
            deleted, _ = Event.objects.all().delete()
            self.stdout.write(f"Удалено событий: {deleted}")

        data = json.loads(path.read_text(encoding="utf-8"))

        created = 0
        for item in data.get("events", []):
            place = None
            if item.get("place_name"):
                place = Place.objects.filter(name=item["place_name"]).first()

            location = None
            if item.get("lng") and item.get("lat"):
                location = Point(item["lng"], item["lat"], srid=4326)

            if place is None and location is None:
                self.stderr.write(f"Пропущено '{item['title']}' — нет ни place, ни координат")
                continue

            starts_at = make_aware(datetime.fromisoformat(item["starts_at"]))
            ends_at = (
                make_aware(datetime.fromisoformat(item["ends_at"])) if item.get("ends_at") else None
            )

            _, was_created = Event.objects.update_or_create(
                title=item["title"],
                starts_at=starts_at,
                defaults={
                    "description": item.get("description", ""),
                    "place": place,
                    "location": location if place is None else None,
                    "ends_at": ends_at,
                    "cover_url": item.get("cover_url", ""),
                },
            )
            if was_created:
                created += 1

        self.stdout.write(self.style.SUCCESS(f"Готово. Новых: {created}"))
