"""Smoke-test для команды seed_places — идемпотентность и парсинг city."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from django.core.management import call_command

from apps.places.models import City, Place, PlaceCategory, PlaceVibe


@pytest.fixture
def fixture_file(tmp_path: Path) -> Path:
    """Минимальная фикстура с meta.city и одним местом + вайбом."""
    data = {
        "meta": {"city": "astana"},
        "categories": [
            {"slug": "cafe", "name_ru": "Кафе"},
        ],
        "places": [
            {
                "name": "Test Cafe",
                "category_slug": "cafe",
                "lat": 51.0908,
                "lng": 71.4187,
                "address": "ул. Тест 1",
                "description": "Тестовое описание",
                "vibes": [{"tag": "calm", "weight": 0.7}],
            }
        ],
    }
    f = tmp_path / "test_seed.json"
    f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return f


@pytest.mark.django_db
class TestSeedPlacesCommand:
    def test_seed_creates_place_with_city(self, fixture_file: Path) -> None:
        # Путь относительный к BASE_DIR — потому передаём абсолютный,
        # подменив BASE_DIR через символическую конкатенацию. В реальности
        # команда читает settings.BASE_DIR / options['file']; для теста
        # положим временный файл прямо в BASE_DIR.
        from django.conf import settings

        target = Path(settings.BASE_DIR) / "_test_seed.json"
        target.write_text(fixture_file.read_text(encoding="utf-8"), encoding="utf-8")

        try:
            call_command("seed_places", file="_test_seed.json")

            assert Place.objects.count() == 1
            place = Place.objects.get(name="Test Cafe")
            assert place.city == City.ASTANA
            assert place.address == "ул. Тест 1"
            assert PlaceCategory.objects.filter(slug="cafe").exists()
            assert PlaceVibe.objects.filter(place=place, tag="calm").count() == 1
        finally:
            target.unlink(missing_ok=True)

    def test_seed_is_idempotent(self, fixture_file: Path) -> None:
        from django.conf import settings

        target = Path(settings.BASE_DIR) / "_test_seed.json"
        target.write_text(fixture_file.read_text(encoding="utf-8"), encoding="utf-8")

        try:
            call_command("seed_places", file="_test_seed.json")
            call_command("seed_places", file="_test_seed.json")

            # После двух вызовов — то же одно место, один вайб
            assert Place.objects.count() == 1
            place = Place.objects.get(name="Test Cafe")
            assert PlaceVibe.objects.filter(place=place).count() == 1
        finally:
            target.unlink(missing_ok=True)