"""Google OAuth: request + response."""
from __future__ import annotations

from rest_framework import serializers


class GoogleAuthRequestSerializer(serializers.Serializer):
    id_token = serializers.CharField(min_length=10, max_length=4096)


class GoogleAuthResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    created = serializers.BooleanField()