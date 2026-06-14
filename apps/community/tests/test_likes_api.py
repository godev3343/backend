"""API-тесты лайков постов и комментариев (идемпотентность, счётчики)."""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.community.models import PostCommentLike, PostLike
from apps.community.tests.factories import PostCommentFactory, PostFactory


@pytest.mark.django_db
class TestPostLikeAPI:
    def test_like_then_unlike(self, authed_client, user) -> None:
        post = PostFactory(author=user)
        url = reverse("community:post_like", kwargs={"post_id": post.id})

        resp = authed_client.post(url)
        assert resp.status_code == 201, resp.data
        assert resp.data["is_liked"] is True
        assert resp.data["likes_count"] == 1
        post.refresh_from_db()
        assert post.likes_count == 1

        # Идемпотентность: повторный POST не множит счётчик.
        resp = authed_client.post(url)
        assert resp.status_code == 200
        assert resp.data["likes_count"] == 1
        assert PostLike.objects.filter(post=post).count() == 1

        resp = authed_client.delete(url)
        assert resp.status_code == 204
        post.refresh_from_db()
        assert post.likes_count == 0
        assert PostLike.objects.filter(post=post).count() == 0

    def test_unlike_when_not_liked_no_underflow(self, authed_client, user) -> None:
        post = PostFactory(author=user, likes_count=0)
        url = reverse("community:post_like", kwargs={"post_id": post.id})
        resp = authed_client.delete(url)
        assert resp.status_code == 204
        post.refresh_from_db()
        assert post.likes_count == 0


@pytest.mark.django_db
class TestCommentLikeAPI:
    def test_like_then_unlike(self, authed_client, user) -> None:
        post = PostFactory(author=user)
        comment = PostCommentFactory(post=post, author=user)
        url = reverse(
            "community:post_comment_like",
            kwargs={"post_id": post.id, "comment_id": comment.id},
        )

        resp = authed_client.post(url)
        assert resp.status_code == 201, resp.data
        assert resp.data["likes_count"] == 1
        comment.refresh_from_db()
        assert comment.likes_count == 1

        resp = authed_client.delete(url)
        assert resp.status_code == 204
        comment.refresh_from_db()
        assert comment.likes_count == 0
        assert PostCommentLike.objects.filter(comment=comment).count() == 0
