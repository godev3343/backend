"""Включаем расширения PostgreSQL для всего проекта."""
from __future__ import annotations

from django.contrib.postgres.operations import (
    BtreeGinExtension,
    TrigramExtension,
    UnaccentExtension,
)
from django.db import migrations


class Migration(migrations.Migration):
    initial = True
    dependencies: list[tuple[str, str]] = []

    operations = [
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS postgis;",
            reverse_sql="DROP EXTENSION IF EXISTS postgis;",
        ),
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS vector;",
            reverse_sql="DROP EXTENSION IF EXISTS vector;",
        ),
        TrigramExtension(),
        UnaccentExtension(),
        BtreeGinExtension(),
    ]