"""API-тесты для /api/places/{id}/reviews и /api/reviews/{id}."""
from __future__ import annotations

import pytest
from django.urls import reverse
from django.utils.timezone import now
from rest_framework import status
from rest_framework.test import APIClient

from apps.places.tests.factories import PlaceFactory
from apps.reviews.models import Review
from apps.reviews.tests.factories import ReviewFactory
from apps.users.tests.factories import UserFactory


def _verified_user(**kwargs):  # type: ignore[no-untyped-def]
    return UserFactory(email_verified_at=now(), **kwargs)


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.mark.django_db
class TestList:
    def test_anon_can_read(self, api_client: APIClient) -> None:
        place = PlaceFactory()
        ReviewFactory.create_batch(3, place=place)

        url = reverse("reviews:place-reviews", kwargs={"place_id": place.pk})
        resp = api_client.get(url)

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["count"] == 3

    def test_returns_in_reverse_chronological(self, api_client: APIClient) -> None:
        place = PlaceFactory()
        r1 = ReviewFactory(place=place)
        r2 = ReviewFactory(place=place)
        r3 = ReviewFactory(place=place)

        url = reverse("reviews:place-reviews", kwargs={"place_id": place.pk})
        resp = api_client.get(url)

        ids = [item["id"] for item in resp.data["results"]]
        assert ids == [r3.pk, r2.pk, r1.pk]


@pytest.mark.django_db
class TestCreate:
    def test_creates(self) -> None:
        user = _verified_user()
        place = PlaceFactory()
        client = APIClient()
        client.force_authenticate(user=user)

        url = reverse("reviews:place-reviews", kwargs={"place_id": place.pk})
        resp = client.post(
            url, data={"rating": 5, "text": "amazing"}, format="json"
        )

        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["rating"] == 5
        assert resp.data["text"] == "amazing"
        assert Review.objects.filter(user=user, place=place).count() == 1

    def test_anon_403(self, api_client: APIClient) -> None:
        place = PlaceFactory()
        url = reverse("reviews:place-reviews", kwargs={"place_id": place.pk})

        resp = api_client.post(url, data={"rating": 5}, format="json")

        assert resp.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_duplicate_409(self) -> None:
        user = _verified_user()
        place = PlaceFactory()
        client = APIClient()
        client.force_authenticate(user=user)
        ReviewFactory(user=user, place=place)

        url = reverse("reviews:place-reviews", kwargs={"place_id": place.pk})
        resp = client.post(url, data={"rating": 1}, format="json")

        assert resp.status_code == status.HTTP_409_CONFLICT
        assert resp.data["code"] == "review_exists"

    def test_invalid_rating(self) -> None:
        user = _verified_user()
        place = PlaceFactory()
        client = APIClient()
        client.force_authenticate(user=user)

        url = reverse("reviews:place-reviews", kwargs={"place_id": place.pk})
        resp = client.post(url, data={"rating": 10}, format="json")

        assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestUpdateDelete:
    def test_patch_own(self) -> None:
        user = _verified_user()
        review = ReviewFactory(user=user, rating=5, text="ok")
        client = APIClient()
        client.force_authenticate(user=user)

        url = reverse("reviews:detail", kwargs={"pk": review.pk})
        resp = client.patch(url, data={"rating": 3, "text": "meh"}, format="json")

        assert resp.status_code == status.HTTP_200_OK
        review.refresh_from_db()
        assert review.rating == 3
        assert review.text == "meh"

    def test_patch_not_own_403(self) -> None:
        owner = _verified_user()
        other = _verified_user()
        review = ReviewFactory(user=owner)
        client = APIClient()
        client.force_authenticate(user=other)

        url = reverse("reviews:detail", kwargs={"pk": review.pk})
        resp = client.patch(url, data={"rating": 1}, format="json")

        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert resp.data["code"] == "not_review_owner"

    def test_delete_own(self) -> None:
        user = _verified_user()
        review = ReviewFactory(user=user)
        client = APIClient()
        client.force_authenticate(user=user)

        url = reverse("reviews:detail", kwargs={"pk": review.pk})
        resp = client.delete(url)

        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert not Review.objects.filter(pk=review.pk).exists()


@pytest.mark.django_db
class TestLike:
    def test_like_increments(self) -> None:
        user = _verified_user()
        review = ReviewFactory()
        client = APIClient()
        client.force_authenticate(user=user)

        url = reverse("reviews:like", kwargs={"pk": review.pk})
        resp = client.post(url)

        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["likes_count"] == 1
        assert resp.data["is_liked"] is True

    def test_double_like_idempotent(self) -> None:
        user = _verified_user()
        review = ReviewFactory()
        client = APIClient()
        client.force_authenticate(user=user)

        url = reverse("reviews:like", kwargs={"pk": review.pk})
        client.post(url)
        resp = client.post(url)

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["likes_count"] == 1

    def test_unlike(self) -> None:
        user = _verified_user()
        review = ReviewFactory()
        client = APIClient()
        client.force_authenticate(user=user)

        like_url = reverse("reviews:like", kwargs={"pk": review.pk})
        client.post(like_url)
        resp = client.delete(like_url)

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["likes_count"] == 0
        assert resp.data["is_liked"] is False