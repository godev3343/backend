"""API-тесты ленты, создания и детали поста."""

from __future__ import annotations

import uuid

import pytest
from django.urls import reverse

from apps.community.models import Post
from apps.community.tests.factories import PostFactory
from apps.social.models import FriendshipStatus
from apps.social.tests.factories import FriendshipFactory


@pytest.mark.django_db
class TestFeedAPI:
    def test_scope_required(self, authed_client) -> None:
        resp = authed_client.get(reverse("community:post_list_create"))
        assert resp.status_code == 400, resp.data

    def test_scope_invalid(self, authed_client) -> None:
        resp = authed_client.get(reverse("community:post_list_create"), {"scope": "nope"})
        assert resp.status_code == 400

    def test_scope_all_returns_all_posts(self, authed_client, user, another_user) -> None:
        PostFactory(author=user)
        PostFactory(author=another_user)

        resp = authed_client.get(reverse("community:post_list_create"), {"scope": "all"})
        assert resp.status_code == 200, resp.data
        # CursorPagination отдаёт {next, previous, results} — без count.
        assert len(resp.data["results"]) == 2

    def test_scope_friends_includes_self_and_friends_only(
        self, authed_client, user, another_user, user_factory
    ) -> None:
        friend = user_factory()
        stranger = user_factory()
        FriendshipFactory(from_user=user, to_user=friend, status=FriendshipStatus.ACCEPTED)

        mine = PostFactory(author=user)
        friends_post = PostFactory(author=friend)
        PostFactory(author=stranger)

        resp = authed_client.get(reverse("community:post_list_create"), {"scope": "friends"})
        assert resp.status_code == 200, resp.data
        ids = {item["id"] for item in resp.data["results"]}
        assert ids == {str(mine.id), str(friends_post.id)}

    def test_feed_pagination_shape(self, authed_client, user) -> None:
        PostFactory(author=user)
        resp = authed_client.get(reverse("community:post_list_create"), {"scope": "all"})
        assert "results" in resp.data
        assert "next" in resp.data
        assert "previous" in resp.data

    def test_requires_auth(self, api_client) -> None:
        resp = api_client.get(reverse("community:post_list_create"), {"scope": "all"})
        assert resp.status_code == 401


@pytest.mark.django_db
class TestCreatePostAPI:
    def test_create_text_only(self, authed_client, user) -> None:
        resp = authed_client.post(
            reverse("community:post_list_create"),
            {"text": "Мой первый пост"},
            format="json",
        )
        assert resp.status_code == 201, resp.data
        assert resp.data["text"] == "Мой первый пост"
        assert resp.data["author"]["id"] == user.pk
        assert resp.data["author"]["display_name"] == user.public_name
        assert resp.data["likes_count"] == 0
        assert resp.data["comments_count"] == 0
        assert resp.data["is_liked"] is False
        assert resp.data["media"] == []
        assert Post.objects.count() == 1

    def test_create_empty_rejected(self, authed_client) -> None:
        resp = authed_client.post(reverse("community:post_list_create"), {}, format="json")
        assert resp.status_code == 400
        assert Post.objects.count() == 0

    def test_create_text_too_long(self, authed_client) -> None:
        resp = authed_client.post(
            reverse("community:post_list_create"),
            {"text": "x" * 1001},
            format="json",
        )
        assert resp.status_code == 400


@pytest.mark.django_db
class TestPostDetailAPI:
    def test_returns_post(self, authed_client, user) -> None:
        post = PostFactory(author=user, likes_count=3)
        resp = authed_client.get(reverse("community:post_detail", kwargs={"post_id": post.id}))
        assert resp.status_code == 200, resp.data
        assert resp.data["id"] == str(post.id)
        assert resp.data["likes_count"] == 3

    def test_missing_post_404(self, authed_client) -> None:
        resp = authed_client.get(reverse("community:post_detail", kwargs={"post_id": uuid.uuid4()}))
        assert resp.status_code == 404
        assert resp.data["code"] == "post_not_found"
