"""Сериализатор карточки события — GET /api/events/{id}."""

from __future__ import annotations

from rest_framework import serializers

from apps.events.serializers.attendance import FriendAttendanceSerializer
from apps.events.serializers.list import EventListItemSerializer
from apps.events.services.attendance import AttendanceService
from apps.events.services.attendance_queries import friends_attending_qs

# Сколько друзей-участников показывать в preview карточки события.
# Полный список — через GET /api/events/{id}/attendance/.
_FRIENDS_PREVIEW_LIMIT = 20


class EventDetailSerializer(EventListItemSerializer):
    """List-shape + description, created_at и attendance-инфо."""

    description = serializers.CharField()
    created_at = serializers.DateTimeField()
    
    attendees_count = serializers.SerializerMethodField()
    is_going = serializers.SerializerMethodField()
    friends_attending = serializers.SerializerMethodField()
    
    def get_attendees_count(self, obj) -> int:
        # Считаем на лету. Если в EventDetailView сделать annotate
        # (attendees_count=Count('attendances')) — оно автоматом подхватится
        # вместо этого SerializerMethodField'а через obj.attendees_count.
        # Но т.к. это endpoint одного объекта (не список) — лишний COUNT 
        # на счёт не давит.
        return AttendanceService.count_for_event(obj.id)
    
    def get_is_going(self, obj) -> bool:
        user = self.context["request"].user
        if not user.is_authenticated:
            return False
        return AttendanceService.is_going(user_id=user.pk, event_id=obj.id)
    
    def get_friends_attending(self, obj) -> list[dict]:
        user = self.context["request"].user
        if not user.is_authenticated:
            return []
        qs = friends_attending_qs(viewer_id=user.pk, event_id=obj.id)
        return FriendAttendanceSerializer(qs[:_FRIENDS_PREVIEW_LIMIT], many=True).data