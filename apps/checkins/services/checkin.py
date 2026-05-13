"""
CheckInService — создание чек-инов.

Ключевые решения:
- Дистанция проверяется через PostGIS `ST_DWithin(geography, geography, 100)`.
  Cast в geography обязателен: на geometry SRID=4326 расстояние интерпретируется
  в градусах. Geography считает в метрах напрямую.
- Бонус FIRST_CHECKIN — отдельный EXISTS-запрос ДО создания чек-ина:
  "первый раз ЭТОГО юзера в ЭТОМ месте". Семантика по бизнес-плану §5.1
  ("первое посещение места"). НЕ путать с социальным "первый среди друзей" —
  такой механики в pre-MVP нет.
- Фото: photo_key — это R2-ключ MediaAsset'а, загруженного через EPIC 4
  (POST /api/upload/presign → /confirm → process_image task). Мы находим
  asset по key + owner=user + purpose=CHECKIN + status=PROCESSED, и создаём
  PlacePhoto, привязанную к Place. Так фото из чек-ина попадает и в галерею
  места, и в фид — естественный shared resource.
- Транзакция: чек-ин, PlacePhoto и points-транзакции — в одной атомарной
  транзакции. Откат любой части откатывает всё. PointsService умеет
  идемпотентность через savepoint внутри.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.gis.geos import Point
from django.db import transaction

from apps.checkins.models import CheckIn
from apps.checkins.services.exceptions import (
    InvalidLocation,
    PhotoNotFound,
    PhotoNotReady,
    PlaceNotFoundForCheckIn,
    TooFarFromPlace,
)
from apps.gamification.models import PointsReason
from apps.gamification.services import PointsService
from apps.places.models import Place, PlacePhoto

if TYPE_CHECKING:
    from apps.users.models import User as UserType


# Максимальная дистанция в метрах между юзером и заведением.
# По ТЗ 6.1: ST_DWithin(..., 100). Не выносим в settings — это бизнес-правило,
# а не переменная окружения; меняется через PR, не через ENV.
MAX_CHECKIN_DISTANCE_M = 100


class CheckInService:
    """Stateless — все методы classmethod."""

    @classmethod
    @transaction.atomic
    def create(
        cls,
        *,
        user: "UserType",
        place_id: int,
        latitude: float,
        longitude: float,
        comment: str = "",
        photo_key: str | None = None,
    ) -> CheckIn:
        """
        Создаёт чек-ин со всеми сайд-эффектами:
        - PlacePhoto (если photo_key передан и валиден).
        - PointsTransaction +5 за чек-ин.
        - PointsTransaction +10 за первый чек-ин юзера в этом месте.

        Все операции в одной транзакции — либо всё, либо ничего.

        Raises:
            InvalidLocation — координаты вне допустимых.
            PlaceNotFoundForCheckIn — place_id не существует.
            TooFarFromPlace — дальше 100м от Place.location.
            PhotoNotFound / PhotoNotReady — проблемы с photo_key.
        """
        cls._validate_coords(latitude, longitude)
        user_point = Point(longitude, latitude, srid=4326)

        place = cls._get_place_or_404(place_id)
        cls._check_distance(place=place, user_point=user_point)

        photo = cls._resolve_photo(user=user, place=place, photo_key=photo_key)

        # Бонус ДО создания чек-ина: иначе текущий чек-ин засчитается
        # как "уже был" и бонус никогда не сработает.
        is_first_at_place = cls._is_users_first_checkin_at_place(
            user_id=user.pk, place_id=place.pk
        )

        checkin = CheckIn.objects.create(
            user=user,
            place=place,
            location=user_point,
            comment=comment,
            photo=photo,
        )

        # Начисление поинтов. Идемпотентно: повтор по тому же checkin.id
        # не создаст вторую транзакцию. На практике дубля быть не должно
        # (мы только что создали checkin), но это страховка для retries.
        PointsService.award(
            user=user,
            reason=PointsReason.CHECKIN,
            ref_type="checkin",
            ref_id=checkin.pk,
        )

        if is_first_at_place:
            PointsService.award(
                user=user,
                reason=PointsReason.FIRST_CHECKIN,
                ref_type="checkin",
                ref_id=checkin.pk,
            )

        return checkin

    # ---------- internal helpers ------------------------------------------

    @staticmethod
    def _validate_coords(latitude: float, longitude: float) -> None:
        if not -90.0 <= latitude <= 90.0 or not -180.0 <= longitude <= 180.0:
            raise InvalidLocation()

    @staticmethod
    def _get_place_or_404(place_id: int) -> Place:
        try:
            return Place.objects.get(pk=place_id)
        except Place.DoesNotExist as exc:
            raise PlaceNotFoundForCheckIn() from exc

    @staticmethod
    def _check_distance(*, place: Place, user_point: Point) -> None:
        """
        Проверяет что user_point в пределах MAX_CHECKIN_DISTANCE_M от place.location.

        Используем ST_DWithin на geography-cast. На geometry SRID=4326 дистанция
        будет в градусах — бесполезно. На geography — в метрах напрямую, и при
        этом учитывается сферичность Земли.

        Реализация через .extra(where=...) — Django ORM lookup `dwithin`
        не умеет geography-cast, а GeoDjango Distance-функция работает
        в единицах SRID. Минимум кода с минимумом сюрпризов.
        """
        within = (
            Place.objects.filter(pk=place.pk)
            .extra(
                where=[
                    "ST_DWithin("
                    "location::geography, "
                    "ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, "
                    "%s"
                    ")"
                ],
                params=[user_point.x, user_point.y, MAX_CHECKIN_DISTANCE_M],
            )
            .exists()
        )
        if not within:
            raise TooFarFromPlace()

    @staticmethod
    def _resolve_photo(
        *,
        user: "UserType",
        place: Place,
        photo_key: str | None,
    ) -> PlacePhoto | None:
        """
        Преобразует photo_key (R2-ключ MediaAsset.key_original) в PlacePhoto.

        Контракт photo_key:
        - MediaAsset должен принадлежать юзеру (owner=user)
        - purpose=CHECKIN
        - status=PROCESSED (process_image отработал)

        Если PlacePhoto на этот asset уже существует (OneToOne) — переиспользуем
        (покрывает retry с тем же photo_key и идемпотентность).
        """
        if photo_key is None:
            return None

        from apps.media.models import MediaAsset, MediaPurpose, MediaStatus

        try:
            asset = MediaAsset.objects.get(
                key_original=photo_key,
                owner=user,
                purpose=MediaPurpose.CHECKIN,
            )
        except MediaAsset.DoesNotExist as exc:
            raise PhotoNotFound() from exc

        if asset.status != MediaStatus.PROCESSED:
            raise PhotoNotReady()

        existing = PlacePhoto.objects.filter(asset=asset).first()
        if existing is not None:
            return existing

        return PlacePhoto.objects.create(
            place=place,
            asset=asset,
            uploaded_by=user,
        )

    @staticmethod
    def _is_users_first_checkin_at_place(*, user_id: int, place_id: int) -> bool:
        """
        True, если у этого юзера ещё нет ни одного чек-ина в этом месте.

        Семантика (бизнес-план §5.1, "первое посещение места"): личный бонус
        за разведку. Не зависит от друзей, не зависит от других юзеров.

        Вызывать ДО CheckIn.objects.create() — иначе только что созданный
        чек-ин сам себе будет помехой.
        """
        return not CheckIn.objects.filter(
            user_id=user_id, place_id=place_id
        ).exists()