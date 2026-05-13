"""
FriendshipService — управление заявками и дружбой.

Дизайн-решения (зафиксированы в EPIC 3 + EPIC 9):
- Одна запись на пару: from_user → to_user. На accept меняем status,
  не создаём зеркальную запись.
- decline = hard delete: позволяет повторно отправить заявку, не плодит
  declined-строки.
- При accept начисляем +5 обоим (PointsReason.FRIEND_ADDED, ref=friendship.pk).
  Идемпотентно: повторный accept уже-accepted дружбы не дублирует поинты.
  После decline + новой accept создаётся новый Friendship с новым pk →
  новое начисление. Это сознательная плата за простоту в pre-MVP; антифрод
  и сезонное обнуление — Этап 1.
- Блокировки (status=BLOCKED) учитываются: ни одна из сторон не может
  отправить заявку другой, пока запись BLOCKED существует.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Q

from apps.gamification.models import PointsReason
from apps.gamification.services import PointsService
from apps.social.models import Friendship, FriendshipStatus
from apps.social.services.exceptions import (
    AlreadyFriends,
    FriendshipExists,
    FriendshipNotFound,
    NotRecipient,
    SelfFriendshipError,
    TargetUserNotFound,
    UserBlocked,
)

if TYPE_CHECKING:
    from apps.users.models import User as UserType

User = get_user_model()


# ref_type для PointsTransaction по дружбе. Константа, чтобы случайно
# не разойтись с тестами или будущими вызовами.
_FRIENDSHIP_REF_TYPE = "friendship"


class FriendshipService:
    """Stateless — все методы classmethod."""

    # ---------- create / accept / decline / cancel -------------------------

    @classmethod
    @transaction.atomic
    def send_request(cls, *, from_user: UserType, to_user_id: int) -> Friendship:
        """
        Отправить заявку от from_user к to_user_id.

        Бросает:
        - SelfFriendshipError — заявка самому себе
        - TargetUserNotFound — to_user_id не существует или is_active=False
        - UserBlocked — между пользователями есть BLOCKED-запись
        - AlreadyFriends — между ними уже accepted
        - FriendshipExists — pending от from_user → to_user уже есть
        """
        if from_user.pk == to_user_id:
            raise SelfFriendshipError()

        try:
            to_user = User.objects.get(pk=to_user_id, is_active=True)
        except User.DoesNotExist as exc:
            raise TargetUserNotFound() from exc

        # Блокируем строки между парой, чтобы избежать гонок при двойном клике.
        existing = list(
            Friendship.objects.select_for_update().filter(
                Q(from_user=from_user, to_user=to_user) | Q(from_user=to_user, to_user=from_user)
            )
        )

        for f in existing:
            if f.status == FriendshipStatus.BLOCKED:
                raise UserBlocked()
            if f.status == FriendshipStatus.ACCEPTED:
                raise AlreadyFriends()
            if f.status == FriendshipStatus.PENDING:
                if f.from_user_id == from_user.pk:
                    # Уже отправлял
                    raise FriendshipExists()
                # Встречная pending-заявка: автоматически принимаем
                # как accept. Это устраняет race, когда оба нажали "добавить"
                # друг другу одновременно.
                f.status = FriendshipStatus.ACCEPTED
                f.save(update_fields=["status"])
                cls._award_friend_added(f, from_user=from_user, to_user=to_user)
                return f

        try:
            return Friendship.objects.create(
                from_user=from_user,
                to_user=to_user,
                status=FriendshipStatus.PENDING,
            )
        except IntegrityError as exc:
            # Гонка между select_for_update и create — крайне маловероятна,
            # но возможна, если другая транзакция вставила запись между ними.
            raise FriendshipExists() from exc

    @classmethod
    @transaction.atomic
    def accept_request(cls, *, user: UserType, friendship_id: int) -> Friendship:
        """
        Принять входящую заявку. Бросает FriendshipNotFound / NotRecipient.

        Идемпотентно: повторный accept уже accepted-заявки возвращает её
        без ошибки и БЕЗ повторного начисления (PointsService.award гарантирует
        идемпотентность по ref_id=friendship.pk).
        """
        try:
            f = Friendship.objects.select_for_update().get(pk=friendship_id)
        except Friendship.DoesNotExist as exc:
            raise FriendshipNotFound() from exc

        if f.to_user_id != user.pk:
            raise NotRecipient()

        if f.status == FriendshipStatus.ACCEPTED:
            return f
        if f.status != FriendshipStatus.PENDING:
            # blocked / неизвестный — не accept
            raise FriendshipNotFound()

        f.status = FriendshipStatus.ACCEPTED
        f.save(update_fields=["status"])

        # Полные User-объекты нужны для F-инкремента points через PointsService.
        # f.from_user/f.to_user не загружены лениво корректно после select_for_update.
        from_user = User.objects.get(pk=f.from_user_id)
        to_user = User.objects.get(pk=f.to_user_id)
        cls._award_friend_added(f, from_user=from_user, to_user=to_user)
        return f

    @classmethod
    @transaction.atomic
    def decline_request(cls, *, user: UserType, friendship_id: int) -> None:
        """
        Отклонить входящую заявку (hard delete).
        Permission: только to_user может отклонить.
        """
        try:
            f = Friendship.objects.select_for_update().get(pk=friendship_id)
        except Friendship.DoesNotExist as exc:
            raise FriendshipNotFound() from exc

        if f.to_user_id != user.pk:
            raise NotRecipient()

        if f.status != FriendshipStatus.PENDING:
            raise FriendshipNotFound()

        f.delete()

    @classmethod
    @transaction.atomic
    def cancel_request(cls, *, user: UserType, friendship_id: int) -> None:
        """
        Отменить исходящую заявку (hard delete).
        Permission: только from_user может отменить.
        """
        try:
            f = Friendship.objects.select_for_update().get(pk=friendship_id)
        except Friendship.DoesNotExist as exc:
            raise FriendshipNotFound() from exc

        if f.from_user_id != user.pk:
            raise NotRecipient()

        if f.status != FriendshipStatus.PENDING:
            raise FriendshipNotFound()

        f.delete()

    # ---------- internal helpers ------------------------------------------

    @staticmethod
    def _award_friend_added(
        friendship: Friendship,
        *,
        from_user: UserType,
        to_user: UserType,
    ) -> None:
        """
        Начислить +5 обоим сторонам новой дружбы.

        Идемпотентно через PointsService (UniqueConstraint на
        user+reason+ref_type+ref_id). Повторный вызов для того же
        friendship.pk вернёт None и ничего не начислит.

        ref_id=friendship.pk: после decline + новой accept создаётся
        новая запись с новым pk → новое начисление. В Этапе 1 (антифрод +
        сезонное обнуление) пересмотрим.
        """
        PointsService.award(
            user=from_user,
            reason=PointsReason.FRIEND_ADDED,
            ref_type=_FRIENDSHIP_REF_TYPE,
            ref_id=friendship.pk,
        )
        PointsService.award(
            user=to_user,
            reason=PointsReason.FRIEND_ADDED,
            ref_type=_FRIENDSHIP_REF_TYPE,
            ref_id=friendship.pk,
        )
