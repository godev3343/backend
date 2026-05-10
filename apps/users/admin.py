# apps/users/admin.py
from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import (
    AdminPasswordChangeForm,
    UserChangeForm,
    UserCreationForm,
)

from apps.users.models import User


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email", "first_name")


class CustomUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"


@admin.register(User)
class CustomUserAdmin(DjangoUserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    change_password_form = AdminPasswordChangeForm
    model = User

    list_display = (
        "id",
        "email",
        "first_name",
        "display_name",
        "phone",
        "points",
        "is_active",
        "date_joined",
    )
    search_fields = ("email", "first_name", "last_name", "display_name", "phone", "google_sub")
    list_filter = ("is_active", "is_staff", "is_superuser")
    ordering = ("-date_joined",)
    readonly_fields = ("google_sub", "date_joined", "last_login")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal", {"fields": ("first_name", "last_name", "phone")}),
        ("External auth", {"fields": ("google_sub",)}),
        ("Profile", {"fields": ("display_name", "avatar_url", "bio")}),
        ("Gamification", {"fields": ("points", "consent_at")}),
        ("Permissions", {
            "fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions"),
        }),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "first_name", "password1", "password2"),
        }),
    )