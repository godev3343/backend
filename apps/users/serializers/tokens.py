"""Сериализатор пары токенов в ответе."""
from __future__ import annotations

from rest_framework import serializers


class TokenPairResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()