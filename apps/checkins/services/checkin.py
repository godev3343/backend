"""
CheckInService — создание чек-инов.

Ключевые решения:
- Дистанция проверяется через PostGIS `ST_DWithin(geography, geography, 100)`.
  Cast в geography обязателен: на geometry SRID=4326 расстояние интерпретируется
  в градусах. Geography считает в метрах напрямую.
- Бонус "first_checkin among friends" — отдельный EXISTS-запрос ДО создания
  чек-ина. Считаем что текущий чек-ин ещё не создан, поэтому он не повлияет
  на собственное условие "среди друзей никто не чек-инился".
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
from django.db.models import Exists, OuterRef, Q

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
from apps.social.models import Friendship, FriendshipStatus

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
        - PointsTransaction +10 за первый чек-ин среди друзей (если применимо).

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
        is_first_among_friends = cls._is_first_checkin_among_friends(
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

        if is_first_among_friends:
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
        within = Place.objects.filter(pk=place.pk).extra(  # noqa: SLF001
            where=[
                "ST_DWithin("
                "location::geography, "
                "ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, "
                "%s"
                ")"
            ],
            params=[user_point.x, user_point.y, MAX_CHECKIN_DISTANCE_M],
        ).exists()

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
        Превращает photo_key в PlacePhoto.

        Алгоритм:
        1. Ищем MediaAsset по (key_original=photo_key, owner=user,
           purpose=CHECKIN, status=PROCESSED).
        2. Если asset уже привязан к PlacePhoto (one-to-one) — переиспользуем
           её. Это покрывает случай retry на /api/checkins с тем же photo_key.
        3. Иначе создаём новую PlacePhoto(place, asset, uploaded_by=user).

        NB: импорт MediaAsset делаем здесь, а не сверху файла — избегаем
        циркулярного импорта (apps.media → ... → apps.checkins в будущем,
        если медиа начнёт ссылаться на чек-ины).
        """
        if not photo_key:
            return None

        from apps.media.models import MediaAsset, MediaPurpose, MediaStatus

        try:
            asset: MediaAsset = MediaAsset.objects.get(
                key_original=photo_key,
                owner=user,
                purpose=MediaPurpose.CHECKIN,
            )
        except MediaAsset.DoesNotExist as exc:
            raise PhotoNotFound() from exc

        if asset.status != MediaStatus.PROCESSED:
            raise PhotoNotReady()

        # OneToOne: если PlacePhoto уже существует на этот asset — берём её.
        existing = PlacePhoto.objects.filter(asset=asset).first()
        if existing is not None:
            return existing

        return PlacePhoto.objects.create(
            place=place,
            asset=asset,
            uploaded_by=user,
        )

    @staticmethod
    def _is_first_checkin_among_friends(*, user_id: int, place_id: int) -> bool:
        """
        True, если бонус "первый среди друзей" должен начислиться.

        Семантика (уточнение к ТЗ 6.1):
        1. У юзера должен быть хотя бы один друг (бонус именно за SOCIAL
           discovery, а не за одинокую вылазку).
        2. Ни сам юзер, ни кто-то из его друзей ещё НЕ чек-инились здесь
           (включаем самого юзера, чтобы повторные чек-ины не крутили бонус).

        Эти два правила вместе исключают пограничные кейсы:
        - юзер без друзей → False
        - повторный чек-ин → False
        - друг уже был → False
        """
        has_friends = Friendship.objects.filter(
            status=FriendshipStatus.ACCEPTED
        ).filter(Q(from_user_id=user_id) | Q(to_user_id=user_id)).exists()

        if not has_friends:
            return False

        friend_ids = Friendship.objects.filter(
            Q(from_user_id=user_id, to_user_id=OuterRef("user_id"))
            | Q(to_user_id=user_id, from_user_id=OuterRef("user_id")),
            status=FriendshipStatus.ACCEPTED,
        )

        anyone_already_checked_in = (
            CheckIn.objects.filter(place_id=place_id)
            .annotate(_is_in_social_net=Exists(friend_ids))
            .filter(Q(user_id=user_id) | Q(_is_in_social_net=True))
            .exists()
        )

        return not anyone_already_checked_in