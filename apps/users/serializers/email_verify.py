"""Email verification: request + confirm."""
from __future__ import annotations

from rest_framework import serializers


class EmailVerifyRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class EmailVerifyConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    code = serializers.RegexField(regex=r"^\d{6}$")