"""
Сборка превью сущности для landing-страницы deep link.

Landing — публичная страница (без авторизации), на неё попадает только тот, у
кого приложение НЕ установлено. Её задача — отдать OG-теги для красивой
карточки в мессенджерах и увести на установку. Поэтому:

- На отсутствующую/невалидную сущность отдаём дженерик-превью, НЕ 404 — иначе
  расшаренная ссылка выглядит битой (см. deep_linking_implementation_guide §2.2).
- Никаких координат/PII в превью: для чек-инов отдаём только имя места, без
  точки пользователя (CLAUDE.md — гео не отдаём сверх продуктовых правил).
- Сборка URL медиа — best-effort: лежащий R2 не должен ронять страницу.

Логика вынесена сюда из view по конвенции (бизнес-логика в services/, не во
view). View остаётся тонким: вызвать build_preview → отрендерить шаблон.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger(__name__)

# Сущности, которые шарятся. Должны совпадать с роутами go_router во Flutter
# и с путями в AndroidManifest/AASA (guide §1).
ENTITY_POST = "posts"
ENTITY_USER = "users"
ENTITY_CHECKIN = "checkins"
ENTITY_PLACE = "places"
ENTITY_EVENT = "events"

# OG-описание режем — мессенджеры показывают ~200 символов.
_DESCRIPTION_LIMIT = 200

_GENERIC_DESCRIPTION = "Места с вайбами, чек-ины и события вокруг. Открой в приложении Go."
_GENERIC_TITLES = {
    ENTITY_POST: "Пост в Go",
    ENTITY_USER: "Профиль в Go",
    ENTITY_CHECKIN: "Чек-ин в Go",
    ENTITY_PLACE: "Место в Go",
    ENTITY_EVENT: "Событие в Go",
}


@dataclass(frozen=True)
class LinkPreview:
    """Данные для OG-тегов и тела landing-страницы."""

    og_type: str
    title: str
    description: str = ""
    image_url: str = ""
    # found=False — дженерик-заглушка (сущности нет/приватна/битый id).
    found: bool = True


def _clip(text: str, limit: int = _DESCRIPTION_LIMIT) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _media_url(getter: Callable[[], str]) -> str:
    """
    URL медиа best-effort. Свойства url_feed/avatar_url дёргают build_public_url,
    который кидает R2Error при неконфигурированном R2 — landing из-за этого
    падать не должен, отдаём пустую строку (превью без картинки валидно).
    """
    try:
        return getter() or ""
    except Exception:
        # Любая ошибка медиа => превью без картинки, landing не падает.
        logger.warning("deeplink: media url build failed", exc_info=True)
        return ""


def _post_preview(entity_id: str) -> LinkPreview | None:
    from apps.community.models import Post, PostMediaType

    post = (
        Post.objects.select_related("author", "author__avatar_asset")
        .filter(pk=uuid.UUID(entity_id))  # ValueError на невалидный UUID
        .first()
    )
    if post is None:
        return None

    media = post.media.filter(type=PostMediaType.IMAGE).order_by("position", "id").first()
    if media is not None:
        image = _media_url(lambda: media.url)
    else:
        image = _media_url(lambda: post.author.avatar_url)

    name = post.author.public_name
    return LinkPreview(
        og_type="article",
        title=f"Пост от {name}" if name else "Пост в Go",
        description=_clip(post.text),
        image_url=image,
    )


def _user_preview(entity_id: str) -> LinkPreview | None:
    from apps.users.models import User

    user = (
        User.objects.select_related("avatar_asset")
        .filter(pk=int(entity_id), is_active=True)  # деактивированный => дженерик
        .first()
    )
    if user is None:
        return None
    return LinkPreview(
        og_type="profile",
        title=user.public_name or "Профиль в Go",
        description=_clip(user.bio),
        image_url=_media_url(lambda: user.avatar_url),
    )


def _place_preview(entity_id: str) -> LinkPreview | None:
    from apps.places.models import Place

    place = Place.objects.filter(pk=int(entity_id)).first()
    if place is None:
        return None
    photo = place.photos.select_related("asset").order_by("-created_at").first()
    image = _media_url(lambda: photo.asset.url_feed) if photo is not None else ""
    return LinkPreview(
        og_type="website",
        title=place.name,
        description=_clip(place.description or place.address),
        image_url=image,
    )


def _checkin_preview(entity_id: str) -> LinkPreview | None:
    from apps.checkins.models import CheckIn

    checkin = (
        CheckIn.objects.select_related("user", "place", "photo__asset")
        .filter(pk=int(entity_id))
        .first()
    )
    if checkin is None:
        return None
    who = checkin.user.public_name
    where = checkin.place.name
    image = _media_url(lambda: checkin.photo.asset.url_feed) if checkin.photo_id else ""
    return LinkPreview(
        og_type="article",
        title=f"{who} — чек-ин в {where}" if who else f"Чек-ин в {where}",
        description=_clip(checkin.comment),
        image_url=image,
    )


def _event_preview(entity_id: str) -> LinkPreview | None:
    from apps.events.models import Event

    event = Event.objects.filter(pk=int(entity_id)).first()
    if event is None:
        return None
    return LinkPreview(
        og_type="website",
        title=event.title,
        description=_clip(event.description),
        image_url=(event.cover_url or ""),
    )


_BUILDERS: dict[str, Callable[[str], LinkPreview | None]] = {
    ENTITY_POST: _post_preview,
    ENTITY_USER: _user_preview,
    ENTITY_CHECKIN: _checkin_preview,
    ENTITY_PLACE: _place_preview,
    ENTITY_EVENT: _event_preview,
}

# Множество поддерживаемых сущностей — используется в URL-роутинге.
SUPPORTED_ENTITIES = frozenset(_BUILDERS)


def _generic(entity: str) -> LinkPreview:
    return LinkPreview(
        og_type="website",
        title=_GENERIC_TITLES.get(entity, "Go — социальная карта города"),
        description=_GENERIC_DESCRIPTION,
        found=False,
    )


def build_preview(entity: str, entity_id: str) -> LinkPreview:
    """
    Превью сущности по (entity, entity_id). Никогда не кидает: на любую проблему
    (неизвестная сущность, битый id, отсутствие в БД) возвращает дженерик —
    landing всегда 200, ссылка в мессенджере не выглядит битой.
    """
    builder = _BUILDERS.get(entity)
    if builder is None:
        return _generic(entity)
    try:
        preview = builder(entity_id)
    except (ValueError, TypeError, ObjectDoesNotExist):
        logger.info("deeplink: preview lookup failed entity=%s id=%s", entity, entity_id)
        preview = None
    return preview if preview is not None else _generic(entity)
