"""GoogleAuthService — верификация id_token, поиск/создание юзера."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils.timezone import now
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from apps.users.services.dto import GoogleProfile, TokenPair
from apps.users.services.exceptions import GoogleAuthError

if TYPE_CHECKING:
    from apps.users.models import User as UserType


class GoogleAuthService:
    """
    Принимает id_token с клиента, верифицирует через Google,
    создаёт/находит пользователя.

    Поведение:
    1. Ищем по google_sub → возвращаем
    2. Ищем по email, привязываем google_sub + email_verified_at → возвращаем
    3. Создаём нового
    """

    @classmethod
    def authenticate(cls, *, id_token: str) -> tuple["UserType", TokenPair, bool]:
        """Возвращает (user, tokens, created)."""
        profile = cls._verify_id_token(id_token)
        user, created = cls._find_or_create_user(profile)
        return user, TokenPair.for_user(user), created

    # ---------- internals --------------------------------------------------

    @classmethod
    def _verify_id_token(cls, id_token: str) -> GoogleProfile:
        client_ids = getattr(settings, "GOOGLE_OAUTH_CLIENT_IDS", None) or []
        if not client_ids:
            raise GoogleAuthError(
                message="GOOGLE_OAUTH_CLIENT_IDS is not configured.",
                code="google_not_configured",
            )

        try:
            # Не передаём audience сюда — проверим вручную против whitelist
            payload: dict[str, Any] = google_id_token.verify_oauth2_token(
                id_token,
                google_requests.Request(),
            )
        except ValueError as exc:
            raise GoogleAuthError(
                message=f"Invalid id_token: {exc}",
                code="invalid_id_token",
            ) from exc

        if payload.get("aud") not in client_ids:
            raise GoogleAuthError(
                message="id_token audience mismatch.",
                code="invalid_audience",
            )

        if not payload.get("email_verified"):
            raise GoogleAuthError(
                message="Google account email is not verified.",
                code="google_email_unverified",
            )

        return GoogleProfile(
            sub=str(payload["sub"]),
            email=str(payload["email"]).lower(),
            email_verified=bool(payload["email_verified"]),
            given_name=str(payload.get("given_name", "")),
            family_name=str(payload.get("family_name", "")),
            picture=str(payload.get("picture", "")),
        )

    @classmethod
    @transaction.atomic
    def _find_or_create_user(cls, profile: GoogleProfile) -> tuple["UserType", bool]:
        from apps.users.models import User

        # 1. По google_sub
        user = User.objects.filter(google_sub=profile.sub).first()
        if user:
            return user, False

        # 2. По email — линкуем
        user = User.objects.select_for_update().filter(email=profile.email).first()
        if user:
            update_fields: list[str] = []
            if not user.google_sub:
                user.google_sub = profile.sub
                update_fields.append("google_sub")
            if user.email_verified_at is None:
                user.email_verified_at = now()
                update_fields.append("email_verified_at")
            if update_fields:
                user.save(update_fields=update_fields)
            return user, False

        # 3. Создаём
        # profile.picture (URL аватара от Google) НЕ сохраняем — аватары в системе
        # хранятся через MediaAsset с EXIF strip / WebP / тремя размерами. Внешний
        # Google-URL без обработки нам не подходит. Юзер загрузит аватар через
        # /api/upload/* во время или после онбординга.
        try:
            user = User.objects.create_user(  # type: ignore[attr-defined]
                email=profile.email,
                first_name=profile.given_name or "User",
                last_name=profile.family_name,
                google_sub=profile.sub,
                email_verified_at=now(),
            )
        except IntegrityError as exc:
            # Гонка между select и create — кто-то успел зарегистрироваться
            user = User.objects.filter(email=profile.email).first()
            if user is None:
                raise GoogleAuthError(
                    message="Failed to create user.",
                    code="user_create_race",
                ) from exc
            return user, False

        return user, True