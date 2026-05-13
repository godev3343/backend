"""Onboarding endpoint."""

from __future__ import annotations

from django.db import transaction
from django.utils.timezone import now
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.serializers import OnboardingRequestSerializer, UserMeSerializer


class OnboardingView(APIView):
    """
    POST /api/users/me/onboarding — заполнить display_name, avatar_url, bio,
    проставить consent_at. Идемпотентно — повторный вызов перезапишет поля.
    """

    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request: Request) -> Response:
        serializer = OnboardingRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = request.user
        user.display_name = data["display_name"]
        user.bio = data.get("bio", "")
        user.consent_at = now()
        user.save(update_fields=["display_name", "bio", "consent_at"])

        return Response(
            UserMeSerializer(
                {
                    "id": user.pk,
                    "email": user.email,
                    "first_name": user.first_name,
                    "display_name": user.display_name,
                    # avatar_url — @property, читает из user.avatar_asset
                    "avatar_url": user.avatar_url,
                    "bio": user.bio,
                    "points": user.points,
                    "is_email_verified": user.is_email_verified,
                    "is_onboarded": user.is_onboarded,
                }
            ).data,
            status=status.HTTP_200_OK,
        )
