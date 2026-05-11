"""
pg_trgm extension + GIN trigram-индексы для быстрого ILIKE-поиска по
display_name и first_name.

Расширение pg_trgm включено в postgres-образ imresamu/postgis:16-3.5-bundle0,
но Django его не активирует — нужен явный CREATE EXTENSION.
"""
from __future__ import annotations

from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0003_user_email_verified_at"),
    ]

    operations = [
        TrigramExtension(),
        migrations.RunSQL(
            sql=[
                # GIN-индексы с gin_trgm_ops для ILIKE/icontains. Поиск
                # 'icontains' с этими индексами работает на порядок быстрее
                # последовательного скана при росте таблицы.
                (
                    "CREATE INDEX IF NOT EXISTS user_display_name_trgm_idx "
                    "ON users_user USING GIN (display_name gin_trgm_ops);"
                ),
                (
                    "CREATE INDEX IF NOT EXISTS user_first_name_trgm_idx "
                    "ON users_user USING GIN (first_name gin_trgm_ops);"
                ),
            ],
            reverse_sql=[
                "DROP INDEX IF EXISTS user_first_name_trgm_idx;",
                "DROP INDEX IF EXISTS user_display_name_trgm_idx;",
            ],
        ),
    ]