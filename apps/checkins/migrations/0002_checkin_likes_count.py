"""Add likes_count to CheckIn (денормализация для EPIC 6)."""
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("checkins", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="checkin",
            name="likes_count",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
