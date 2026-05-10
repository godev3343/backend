"""GIN-индексы для поиска: display_name и first_name."""
from __future__ import annotations

from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0001_initial"),
        ("core", "0001_initial"),
    ]

    operations = [
        TrigramExtension(),
        migrations.RunSQL(
            sql=(
                "CREATE INDEX IF NOT EXISTS user_display_name_trgm_idx "
                "ON users_user USING gin (display_name gin_trgm_ops); "
                "CREATE INDEX IF NOT EXISTS user_first_name_trgm_idx "
                "ON users_user USING gin (first_name gin_trgm_ops);"
            ),
            reverse_sql=(
                "DROP INDEX IF EXISTS user_display_name_trgm_idx; "
                "DROP INDEX IF EXISTS user_first_name_trgm_idx;"
            ),
        ),
    ]