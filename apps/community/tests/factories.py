from __future__ import annotations

import factory
from factory.django import DjangoModelFactory

from apps.community.models import Post, PostComment
from apps.users.tests.factories import UserFactory


class PostFactory(DjangoModelFactory):
    class Meta:
        model = Post

    author = factory.SubFactory(UserFactory)
    text = factory.Sequence(lambda n: f"post text {n}")


class PostCommentFactory(DjangoModelFactory):
    class Meta:
        model = PostComment

    post = factory.SubFactory(PostFactory)
    author = factory.SubFactory(UserFactory)
    text = factory.Sequence(lambda n: f"comment {n}")


__all__ = ("PostCommentFactory", "PostFactory")
