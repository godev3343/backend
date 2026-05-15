"""
Reviews endpoints:
- GET    /api/places/{id}/reviews        — список отзывов места
- POST   /api/places/{id}/reviews        — создать свой отзыв (один на место)
- PATCH  /api/reviews/{id}               — обновить свой
- DELETE /api/reviews/{id}               — удалить свой
- POST   /api/reviews/{id}/like          — лайкнуть (идемпотентно)
- DELETE /api/reviews/{id}/like          — снять лайк (идемпотентно)
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.reviews.models import Review, ReviewLike
from apps.reviews.serializers import (
    ReviewCreateSerializer,
    ReviewSerializer,
    ReviewUpdateSerializer,
)
from apps.reviews.services import ReviewLikeService, ReviewService
from apps.users.permissions import IsEmailVerified

from drf_spectacular.utils import extend_schema

from apps.core.serializers import DetailSerializer, EmptySerializer


@extend_schema(request=EmptySerializer, responses=DetailSerializer, tags=["auth"])
class PlaceReviewsView(GenericAPIView):
    """GET list + POST create отзывов для конкретного place."""

    serializer_class = ReviewSerializer
    pagination_class = LimitOffsetPagination

    def get_permissions(self):  # type: ignore[no-untyped-def]
        if self.request.method == "POST":
            return [IsAuthenticated(), IsEmailVerified()]
        return [IsAuthenticatedOrReadOnly()]

    def get(self, request: Request, place_id: int) -> Response:
        qs = (
            Review.objects.filter(place_id=place_id)
            .select_related("user", "photo", "photo__asset")
            .order_by("-created_at", "-id")
        )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        page_list = list(page) if page is not None else list(qs)

        liked_ids: set[int] = set()
        if request.user.is_authenticated and page_list:
            liked_ids = set(
                ReviewLike.objects.filter(
                    user_id=request.user.pk,
                    review_id__in=[r.id for r in page_list],
                ).values_list("review_id", flat=True)
            )

        serializer = self.get_serializer(
            page_list,
            many=True,
            context={"request": request, "liked_review_ids": liked_ids},
        )

        if page is not None:
            return paginator.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def post(self, request: Request, place_id: int) -> Response:
        serializer = ReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        review = ReviewService.create(
            user=request.user,
            place_id=place_id,
            rating=serializer.validated_data["rating"],
            text=serializer.validated_data["text"],
            photo_key=serializer.validated_data["photo_key"],
        )

        output = ReviewSerializer(
            review,
            context={"request": request, "liked_review_ids": set()},
        )
        return Response(output.data, status=status.HTTP_201_CREATED)


@extend_schema(request=EmptySerializer, responses=DetailSerializer, tags=["auth"])
class ReviewDetailView(APIView):
    """PATCH + DELETE на свой отзыв."""

    permission_classes = [IsAuthenticated, IsEmailVerified]

    def patch(self, request: Request, pk: int) -> Response:
        serializer = ReviewUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Различаем "поле не передано" vs "передано как null".
        # ReviewUpdateSerializer.photo_key с allow_null + required=False —
        # если ключа нет в request.data → не в validated_data;
        # если ключ есть с null → попадёт в validated_data как None.
        if "photo_key" in data:
            photo_key = data["photo_key"]
            clear_photo = photo_key is None
        else:
            photo_key = None
            clear_photo = False

        review = ReviewService.update(
            user=request.user,
            review_id=pk,
            rating=data.get("rating"),
            text=data.get("text"),
            photo_key=photo_key,
            clear_photo=clear_photo,
        )

        output = ReviewSerializer(
            review,
            context={"request": request, "liked_review_ids": set()},
        )
        return Response(output.data)

    def delete(self, request: Request, pk: int) -> Response:
        ReviewService.delete(user=request.user, review_id=pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(request=EmptySerializer, responses=DetailSerializer, tags=["auth"])
class ReviewLikeView(APIView):
    """POST + DELETE лайка на отзыв. Идемпотентно."""

    permission_classes = [IsAuthenticated, IsEmailVerified]

    def post(self, request: Request, pk: int) -> Response:
        result = ReviewLikeService.like(user=request.user, review_id=pk)
        review = Review.objects.only("likes_count").get(pk=pk)
        return Response(
            {
                "result": result,
                "likes_count": review.likes_count,
                "is_liked": True,
            },
            status=(
                status.HTTP_201_CREATED if result == "created"
                else status.HTTP_200_OK
            ),
        )

    def delete(self, request: Request, pk: int) -> Response:
        ReviewLikeService.unlike(user=request.user, review_id=pk)
        review = Review.objects.only("likes_count").get(pk=pk)
        return Response(
            {
                "likes_count": review.likes_count,
                "is_liked": False,
            }
        )