"""DTO для auth-сервисов. Только данные, никакой логики."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rest_framework_simplejwt.tokens import RefreshToken

if TYPE_CHECKING:
    from apps.users.models import User as UserType


@dataclass(frozen=True)
class TokenPair:
    """Пара access + refresh JWT."""

    access: str
    refresh: str

    @classmethod
    def for_user(cls, user: UserType) -> TokenPair:
        refresh = RefreshToken.for_user(user)
        return cls(access=str(refresh.access_token), refresh=str(refresh))


@dataclass(frozen=True)
class GoogleProfile:
    """Распарсенный и провалидированный payload Google id_token."""

    sub: str
    email: str
    email_verified: bool
    given_name: str
    family_name: str
    picture: str
