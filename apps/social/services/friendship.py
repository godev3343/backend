# apps/social/services/friendship.py
"""
FriendshipService — управление заявками и дружбой.

Дизайн-решения (зафиксированы в EPIC 3):
- Одна запись на пару: from_user → to_user. На accept меняем status,
  не создаём зеркальную запись.
- decline = hard delete: позволяет повторно отправить заявку, не плодит
  declined-строки.
- Поинты НЕ начисляются в EPIC 3 (хук-комментарий в accept — для EPIC 9).
- Блокировки (status=BLOCKED) учитываются: ни одна из сторон не может
  отправить заявку другой, пока запись BLOCKED существует.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Q

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


class FriendshipService:
    """Stateless — все методы classmethod."""

    # ---------- create / accept / decline / cancel -------------------------

    @classmethod
    @transaction.atomic
    def send_request(cls, *, from_user: "UserType", to_user_id: int) -> Friendship:
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
                Q(from_user=from_user, to_user=to_user)
                | Q(from_user=to_user, to_user=from_user)
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
                # TODO(EPIC 9): начислить поинты обоим (PointsService.award)
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
    def accept_request(
        cls, *, user: "UserType", friendship_id: int
    ) -> Friendship:
        """
        Принять входящую заявку. Бросает FriendshipNotFound / NotRecipient.

        Идемпотентно: повторный accept уже accepted-заявки возвращает её
        без ошибки.
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
        # TODO(EPIC 9): начислить поинты обоим (PointsService.award)
        return f

    @classmethod
    @transaction.atomic
    def decline_request(cls, *, user: "UserType", friendship_id: int) -> None:
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
    def cancel_request(cls, *, user: "UserType", friendship_id: int) -> None:
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

    @classmethod
    @transaction.atomic
    def remove_friend(cls, *, user: "UserType", other_user_id: int) -> None:
        """
        Удалить дружбу с other_user_id. Удаляет accepted-запись в любом
        направлении. Бросает FriendshipNotFound, если друзьями не были.
        """
        deleted, _ = Friendship.objects.filter(
            Q(from_user=user, to_user_id=other_user_id)
            | Q(from_user_id=other_user_id, to_user=user),
            status=FriendshipStatus.ACCEPTED,
        ).delete()
        if deleted == 0:
            raise FriendshipNotFound()

    # ---------- queries ----------------------------------------------------

    @classmethod
    def incoming_requests(cls, *, user: "UserType"):  # type: ignore[no-untyped-def]
        """Pending-заявки, где user = to_user."""
        return (
            Friendship.objects.filter(
                to_user=user, status=FriendshipStatus.PENDING
            )
            .select_related("from_user")
            .order_by("-created_at")
        )

    @classmethod
    def outgoing_requests(cls, *, user: "UserType"):  # type: ignore[no-untyped-def]
        """Pending-заявки, где user = from_user."""
        return (
            Friendship.objects.filter(
                from_user=user, status=FriendshipStatus.PENDING
            )
            .select_related("to_user")
            .order_by("-created_at")
        )

    @classmethod
    def list_friends(cls, *, user: "UserType"):  # type: ignore[no-untyped-def]
        """
        Список юзеров, с которыми user в accepted-дружбе.
        Возвращает QuerySet[User] (counterparts), не Friendship.
        """
        # IDs друзей: все записи где (from=user or to=user) и accepted.
        # Берём counterparty в каждом направлении.
        outgoing_ids = Friendship.objects.filter(
            from_user=user, status=FriendshipStatus.ACCEPTED
        ).values_list("to_user_id", flat=True)
        incoming_ids = Friendship.objects.filter(
            to_user=user, status=FriendshipStatus.ACCEPTED
        ).values_list("from_user_id", flat=True)

        friend_ids = list(outgoing_ids) + list(incoming_ids)
        return User.objects.filter(pk__in=friend_ids).order_by("display_name", "id")

    @classmethod
    def is_friends(cls, *, user_a_id: int, user_b_id: int) -> bool:
        """Хелпер для других сервисов (EPIC 6 — feed, EPIC 7 — события)."""
        if user_a_id == user_b_id:
            return False
        return Friendship.objects.filter(
            Q(from_user_id=user_a_id, to_user_id=user_b_id)
            | Q(from_user_id=user_b_id, to_user_id=user_a_id),
            status=FriendshipStatus.ACCEPTED,
        ).exists()