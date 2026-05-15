"""
seed_achievements — идемпотентный сидинг каталога ачивок.

Запускается:
- автоматом в `just setup` через `just seed-achievements`
- руками после обновления fixture: `just seed-achievements`
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.gamification.models import Achievement


class Command(BaseCommand):
    help = "Сидинг каталога Achievement из fixtures/achievements.json"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--file",
            default="apps/gamification/fixtures/achievements.json",
            help="Путь к fixture-файлу относительно BASE_DIR",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        path = Path(settings.BASE_DIR) / options["file"]
        if not path.exists():
            self.stderr.write(self.style.ERROR(f"Не найден файл {path}"))
            return

        with path.open(encoding="utf-8") as f:
            data = json.load(f)

        created = 0
        updated = 0
        for item in data["achievements"]:
            obj, was_created = Achievement.objects.update_or_create(
                code=item["code"],
                defaults={
                    "name_ru": item["name_ru"],
                    "description_ru": item["description_ru"],
                    "icon_url": item.get("icon_url", ""),
                    "order": item.get("order", 100),
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Готово. Создано: {created}, обновлено: {updated}"
            )
        )