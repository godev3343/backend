"""factory_boy-фабрики для MediaAsset."""
from __future__ import annotations

import factory

from apps.media.models import MediaAsset, MediaPurpose, MediaStatus
from apps.users.tests.factories import UserFactory


class MediaAssetFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MediaAsset

    owner = factory.SubFactory(UserFactory)
    purpose = MediaPurpose.AVATAR
    status = MediaStatus.PENDING
    key_original = factory.LazyAttribute(
        lambda a: f"avatars/{a.owner.pk}/abc123/original.jpg"
    )
    key_feed = ""
    key_thumb = ""
    width = 0
    height = 0
    source_bytes = 0