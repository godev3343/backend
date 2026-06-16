"""Landing-страница шаринга: роутинг, дженерик-заглушка и реальное превью."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db

_MISSING_UUID = "00000000-0000-0000-0000-000000000000"


def test_unknown_entity_is_404(client):
    # re_path ограничен 5 сущностями — посторонний корневой путь не перехватываем.
    resp = client.get("/widgets/123")
    assert resp.status_code == 404


def test_missing_entity_renders_generic_not_404(client):
    # Сущности нет → дженерик-превью + 200 (ссылка в мессенджере не битая).
    resp = client.get(f"/posts/{_MISSING_UUID}")

    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Открой в приложении Go" in html
    assert 'property="og:title"' in html


def test_landing_trailing_slash_does_not_redirect(client):
    # Слеш на конце опционален (`/?`) — App Links не любят 301.
    resp = client.get(f"/posts/{_MISSING_UUID}/")
    assert resp.status_code == 200


def test_post_preview_renders_og_tags(client):
    from apps.community.tests.factories import PostFactory

    post = PostFactory(text="привет мир")

    resp = client.get(f"/posts/{post.id}")

    assert resp.status_code == 200
    html = resp.content.decode()
    assert 'property="og:type" content="article"' in html
    assert "привет мир" in html
    assert post.author.public_name in html


def test_place_preview_uses_place_name(client):
    from apps.places.tests.factories import PlaceFactory

    place = PlaceFactory(name="Кофейня Лайм")

    resp = client.get(f"/places/{place.id}")

    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Кофейня Лайм" in html
    assert 'property="og:type" content="website"' in html


def test_play_store_button_shown_when_configured(client, settings):
    settings.PLAY_STORE_URL = "https://play.google.com/store/apps/details?id=com.go.app.go_app"

    resp = client.get(f"/posts/{_MISSING_UUID}")

    html = resp.content.decode()
    assert settings.PLAY_STORE_URL in html
    assert "Открыть в приложении Go" in html
