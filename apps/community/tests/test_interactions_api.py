"""API-тесты репостов и просмотров."""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.community.models import PostView
from apps.community.tests.factories import PostFactory


@pytest.mark.django_db
class TestShareAPI:
    def test_share_increments(self, authed_client, user) -> None:
        post = PostFactory(author=user)
        url = reverse("community:post_share", kwargs={"post_id": post.id})

        resp = authed_client.post(url)
        assert resp.status_code == 200, resp.data
        assert resp.data["shares_count"] == 1

        authed_client.post(url)
        post.refresh_from_db()
        assert post.shares_count == 2


@pytest.mark.django_db
class TestViewAPI:
    def test_view_dedup_same_day(self, authed_client, user) -> None:
        post = PostFactory(author=user)
        url = reverse("community:post_view", kwargs={"post_id": post.id})

        resp = authed_client.post(url)
        assert resp.status_code == 200, resp.data
        assert resp.data["views_count"] == 1

        # Повторный просмотр тем же юзером в тот же день не накручивает.
        resp = authed_client.post(url)
        assert resp.data["views_count"] == 1
        post.refresh_from_db()
        assert post.views_count == 1
        assert PostView.objects.filter(post=post, user=user).count() == 1

    def test_view_counts_distinct_users(self, authed_client, another_authed_client, user) -> None:
        post = PostFactory(author=user)
        url = reverse("community:post_view", kwargs={"post_id": post.id})

        authed_client.post(url)
        another_authed_client.post(url)

        post.refresh_from_db()
        assert post.views_count == 2
