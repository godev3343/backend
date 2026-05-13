from django.contrib import admin

from apps.social.models import Friendship


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ("id", "from_user", "to_user", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("from_user__display_name", "to_user__display_name")
    raw_id_fields = ("from_user", "to_user")
