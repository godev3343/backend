"""API-тесты комментариев."""

from __future__ import annotations

import uuid

import pytest
from django.urls import reverse

from apps.community.models import PostComment
from apps.community.tests.factories import PostCommentFactory, PostFactory


@pytest.mark.django_db
class TestCommentsAPI:
    def test_create_increments_count(self, authed_client, user) -> None:
        post = PostFactory(author=user)
        resp = authed_client.post(
            reverse("community:post_comments", kwargs={"post_id": post.id}),
            {"text": "Огонь!"},
            format="json",
        )
        assert resp.status_code == 201, resp.data
        assert resp.data["text"] == "Огонь!"
        assert resp.data["post_id"] == str(post.id)
        assert resp.data["author"]["id"] == user.pk
        assert resp.data["is_liked"] is False

        post.refresh_from_db()
        assert post.comments_count == 1
        assert PostComment.objects.filter(post=post).count() == 1

    def test_create_empty_rejected(self, authed_client, user) -> None:
        post = PostFactory(author=user)
        resp = authed_client.post(
            reverse("community:post_comments", kwargs={"post_id": post.id}),
            {"text": "   "},
            format="json",
        )
        assert resp.status_code == 400

    def test_create_on_missing_post_404(self, authed_client) -> None:
        resp = authed_client.post(
            reverse("community:post_comments", kwargs={"post_id": uuid.uuid4()}),
            {"text": "hi"},
            format="json",
        )
        assert resp.status_code == 404
        assert resp.data["code"] == "post_not_found"

    def test_list_order_asc(self, authed_client, user) -> None:
        post = PostFactory(author=user)
        c1 = PostCommentFactory(post=post, author=user)
        c2 = PostCommentFactory(post=post, author=user)

        resp = authed_client.get(reverse("community:post_comments", kwargs={"post_id": post.id}))
        assert resp.status_code == 200, resp.data
        ids = [item["id"] for item in resp.data["results"]]
        assert ids == [str(c1.id), str(c2.id)]
