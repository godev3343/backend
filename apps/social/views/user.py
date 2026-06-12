# apps/social/views/user.py
"""
Эндпоинты пользователей:
- GET/PATCH /api/users/me
- GET /api/users/{id}
- GET /api/users/search?q=...

Profile endpoints разделены: GET/PATCH /me требуют только аутентификации
(чтобы юзер мог редактировать профиль ДО онбординга в EPIC 2-флоу),
а просмотр чужих профилей и поиск требуют IsOnboarded.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.generics import GenericAPIView
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.social.models import FriendshipStatus
from apps.social.serializers import (
    UserMeSerializer,
    UserMeUpdateSerializer,
    UserPublicSerializer,
    UserSearchResultSerializer,
)
from apps.social.services import annotate_friendship_status
from apps.social.throttling import UserSearchThrottle
from apps.users.permissions import IsOnboarded

from drf_spectacular.utils import OpenApiParameter, extend_schema

from apps.core.serializers import DetailSerializer

User = get_user_model()

# Поля, которые юзер может обновлять через PATCH /me.
_UPDATABLE_ME_FIELDS = (
    "first_name",
    "last_name",
    "display_name",
    "bio",
    "preferred_vibes",
    "ai_context",
)


def _user_me_with_counts(user_id: int):  # type: ignore[no-untyped-def]
    """
    Возвращает User с аннотациями friends_count и checkins_count.
    Друзья — только accepted, считаем в обе стороны.
    """
    return (
        User.objects.filter(pk=user_id)
        .select_related("avatar_asset")
        .annotate(
            checkins_count=Count("checkins", distinct=True),
            # friends_count = accepted-записи где user from OR to
            friends_count=(
                Count(
                    "friendships_sent",
                    filter=Q(friendships_sent__status=FriendshipStatus.ACCEPTED),
                    distinct=True,
                )
                + Count(
                    "friendships_received",
                    filter=Q(friendships_received__status=FriendshipStatus.ACCEPTED),
                    distinct=True,
                )
            ),
        )
        .get()
    )


def _serialize_me(user) -> dict:  # type: ignore[no-untyped-def]
    """Собирает payload для UserMeSerializer из User с аннотациями."""
    return UserMeSerializer(user).data


class UserMeView(APIView):
    """GET и PATCH /api/users/me."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["users"],
        summary="Мой профиль",
        description=(
            "Полный приватный профиль текущего пользователя, включая email, "
            "счётчики друзей и чек-инов, поинты, статус и AI-предпочтения "
            "(`preferred_vibes`, `ai_context`)."
        ),
        responses={200: UserMeSerializer, 401: DetailSerializer},
    )
    def get(self, request: Request) -> Response:
        user = _user_me_with_counts(request.user.pk)
        return Response(_serialize_me(user), status=status.HTTP_200_OK)

    @extend_schema(
        tags=["users"],
        summary="Обновить мой профиль",
        description=(
            "Частичное обновление профиля. Передавайте только изменяемые поля "
            "(нужно минимум одно): `first_name`, `last_name`, `display_name`, "
            "`bio`, `preferred_vibes`, `ai_context`.\n\n"
            "Email/пароль здесь не меняются (это auth-флоу), аватар грузится "
            "через `/api/upload/*`. Для полной замены AI-настроек есть отдельный "
            "идемпотентный `PUT /api/users/me/preferences`. Возвращает "
            "обновлённый профиль."
        ),
        request=UserMeUpdateSerializer,
        responses={200: UserMeSerializer, 400: DetailSerializer, 401: DetailSerializer},
    )
    def patch(self, request: Request) -> Response:
        serializer = UserMeUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        user = request.user
        update_fields: list[str] = []
        for field in _UPDATABLE_ME_FIELDS:
            if field in validated:
                setattr(user, field, validated[field])
                update_fields.append(field)

        if update_fields:
            user.save(update_fields=update_fields)

        # Возвращаем актуальное состояние с counts
        user = _user_me_with_counts(user.pk)
        return Response(_serialize_me(user), status=status.HTTP_200_OK)


@extend_schema(
    tags=["social"],
    summary="Публичный профиль пользователя",
    description=(
        "Публичный профиль другого пользователя по id. Скрыты приватные поля "
        "(email, телефон, `ai_context` и т.п.). Включает статус дружбы с текущим "
        "пользователем (`friendship_status`, `friendship_id`) — фронт рисует "
        "соответствующую кнопку.\n\n"
        "Требует пройденного онбординга. Возвращает 404, если пользователь не "
        "найден или неактивен."
    ),
    responses={200: UserPublicSerializer, 401: DetailSerializer, 403: DetailSerializer, 404: DetailSerializer},
)
class UserPublicView(APIView):
    """GET /api/users/{id} — публичный профиль другого юзера."""

    permission_classes = [IsAuthenticated, IsOnboarded]

    def get(self, request: Request, user_id: int) -> Response:
        qs = (
            User.objects.filter(pk=user_id, is_active=True)
            .select_related("avatar_asset")
            .annotate(
                checkins_count=Count("checkins", distinct=True),
                friends_count=(
                    Count(
                        "friendships_sent",
                        filter=Q(friendships_sent__status=FriendshipStatus.ACCEPTED),
                        distinct=True,
                    )
                    + Count(
                        "friendships_received",
                        filter=Q(friendships_received__status=FriendshipStatus.ACCEPTED),
                        distinct=True,
                    )
                ),
            )
        )
        qs = annotate_friendship_status(qs, viewer_id=request.user.pk)
        user = qs.first()
        if user is None:
            raise NotFound("User not found.")
        return Response(UserPublicSerializer(user).data, status=status.HTTP_200_OK)


@extend_schema(
    tags=["social"],
    summary="Поиск пользователей",
    description=(
        "Поиск пользователей по `q` (минимум 2 символа): совпадение по "
        "`display_name`/`first_name` (без учёта регистра) либо точный e-mail. "
        "Текущий пользователь из выдачи исключается. При `q` короче 2 символов "
        "возвращается пустой результат.\n\n"
        "Требует пройденного онбординга. Пагинация limit/offset (максимум 20 на "
        "страницу). Throttling по пользователю."
    ),
    parameters=[
        OpenApiParameter(
            name="q",
            type=str,
            location=OpenApiParameter.QUERY,
            required=True,
            description="Поисковый запрос, минимум 2 символа.",
        ),
    ],
    responses={200: UserSearchResultSerializer(many=True), 401: DetailSerializer, 403: DetailSerializer},
)
class UserSearchView(GenericAPIView):
    """
    GET /api/users/search?q=...&limit=&offset=

    Минимум 2 символа в q. Поиск по display_name и first_name (icontains),
    плюс точный email-матч. Текущего юзера из выдачи исключаем.
    """

    permission_classes = [IsAuthenticated, IsOnboarded]
    throttle_classes = [UserSearchThrottle]
    pagination_class = LimitOffsetPagination
    serializer_class = UserSearchResultSerializer
    # Запрос строится вручную в get(); queryset нужен только для генерации
    # схемы drf-spectacular.
    queryset = User.objects.none()

    MIN_QUERY_LEN = 2
    MAX_LIMIT = 20

    def get(self, request: Request) -> Response:
        q = (request.query_params.get("q") or "").strip()
        if len(q) < self.MIN_QUERY_LEN:
            return Response(
                {"results": [], "count": 0, "next": None, "previous": None},
                status=status.HTTP_200_OK,
            )

        qs = (
            User.objects.filter(is_active=True)
            .exclude(pk=request.user.pk)
            .select_related("avatar_asset")
            .filter(Q(display_name__icontains=q) | Q(first_name__icontains=q) | Q(email__iexact=q))
        )
        qs = annotate_friendship_status(qs, viewer_id=request.user.pk).order_by(
            "display_name", "id"
        )

        paginator = self.pagination_class()
        paginator.default_limit = self.MAX_LIMIT
        paginator.max_limit = self.MAX_LIMIT
        page = paginator.paginate_queryset(qs, request, view=self)
        serializer = self.get_serializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
