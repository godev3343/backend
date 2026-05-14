"""Idempotent создание суперюзера из env vars. Для деплоя."""

from __future__ import annotations

import os

from django.core.management.base import BaseCommand, CommandError

from apps.users.models import User


class Command(BaseCommand):
    help = "Создать суперюзера из DJANGO_SUPERUSER_* env vars, если ни одного ещё нет."

    def handle(self, *args: object, **options: object) -> None:
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(self.style.WARNING("Суперюзер уже есть, пропускаю."))
            return

        email = os.environ.get("DJANGO_SUPERUSER_EMAIL")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")

        if not email or not password:
            raise CommandError(
                "Нужны DJANGO_SUPERUSER_EMAIL и DJANGO_SUPERUSER_PASSWORD в env."
            )

        user = User.objects.create_superuser(email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Создан суперюзер: {user.email}"))