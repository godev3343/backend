"""Сериализаторы для attendance-эндпоинтов и nested-полей в Event."""

from __future__ import annotations

from rest_framework import serializers

from apps.events.models import EventAttendance


class _AttendingUserBriefSerializer(serializers.Serializer):
    """
    Минимальный shape юзера для списка идущих.
    Те же поля что в social._UserBriefSerializer — но не наследуем оттуда:
    публичный shape attendance-эндпоинтов не должен зависеть от social-app
    (если там поменяют brief — мы не должны автоматом меняться).
    """

    id = serializers.IntegerField()
    display_name = serializers.CharField(source="public_name", read_only=True)
    avatar_url = serializers.URLField(allow_blank=True, allow_null=True)


class FriendAttendanceSerializer(serializers.ModelSerializer):
    """Элемент списка друзей-участников события."""

    user = _AttendingUserBriefSerializer(read_only=True)

    class Meta:
        model = EventAttendance
        fields = ("user", "created_at")


class EventAttendanceStateSerializer(serializers.Serializer):
    """
    Ответ на GET / POST / DELETE /api/events/{id}/attendance/.
    Полное состояние, чтобы фронт мог разово отрисовать кнопку и счётчик.
    """

    is_going = serializers.BooleanField()
    attendees_count = serializers.IntegerField()
    friends_attending = FriendAttendanceSerializer(many=True)