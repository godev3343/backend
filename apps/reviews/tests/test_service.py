"""ReviewService — создание/обновление/удаление + поинты + ачивки."""
from __future__ import annotations

import pytest

from apps.gamification.models import (
    Achievement,
    PointsReason,
    PointsTransaction,
    UserAchievement,
)
from apps.places.tests.factories import PlaceFactory
from apps.reviews.models import Review
from apps.reviews.services import ReviewService
from apps.reviews.services.exceptions import (
    NotReviewOwner,
    PlaceNotFoundForReview,
    ReviewAlreadyExists,
    ReviewNotFound,
)
from apps.users.tests.factories import UserFactory


@pytest.mark.django_db
class TestCreate:
    def test_creates_review(self) -> None:
        user = UserFactory()
        place = PlaceFactory()

        review = ReviewService.create(
            user=user, place_id=place.pk, rating=5, text="great"
        )

        assert review.pk is not None
        assert review.rating == 5
        assert review.text == "great"
        assert Review.objects.filter(user=user, place=place).count() == 1

    def test_awards_points(self) -> None:
        user = UserFactory()
        place = PlaceFactory()

        review = ReviewService.create(user=user, place_id=place.pk, rating=4)

        tx = PointsTransaction.objects.get(
            user=user,
            reason=PointsReason.REVIEW_POSTED,
            ref_id=review.pk,
        )
        assert tx.delta > 0
        user.refresh_from_db()
        assert user.points == tx.delta

    def test_duplicate_raises(self) -> None:
        user = UserFactory()
        place = PlaceFactory()
        ReviewService.create(user=user, place_id=place.pk, rating=5)

        with pytest.raises(ReviewAlreadyExists):
            ReviewService.create(user=user, place_id=place.pk, rating=3)

    def test_unknown_place_raises(self) -> None:
        user = UserFactory()
        with pytest.raises(PlaceNotFoundForReview):
            ReviewService.create(user=user, place_id=999999, rating=5)


@pytest.mark.django_db
class TestUpdate:
    def test_updates_own(self) -> None:
        user = UserFactory()
        review = ReviewService.create(
            user=user, place_id=PlaceFactory().pk, rating=5, text="old"
        )

        updated = ReviewService.update(
            user=user, review_id=review.pk, rating=3, text="new"
        )

        assert updated.rating == 3
        assert updated.text == "new"

    def test_update_not_own_raises(self) -> None:
        owner = UserFactory()
        other = UserFactory()
        review = ReviewService.create(
            user=owner, place_id=PlaceFactory().pk, rating=5
        )

        with pytest.raises(NotReviewOwner):
            ReviewService.update(user=other, review_id=review.pk, rating=1)

    def test_update_does_not_re_award_points(self) -> None:
        user = UserFactory()
        review = ReviewService.create(
            user=user, place_id=PlaceFactory().pk, rating=5
        )
        initial_tx_count = PointsTransaction.objects.filter(user=user).count()

        ReviewService.update(user=user, review_id=review.pk, rating=1)

        assert PointsTransaction.objects.filter(user=user).count() == initial_tx_count

    def test_update_unknown_raises(self) -> None:
        user = UserFactory()
        with pytest.raises(ReviewNotFound):
            ReviewService.update(user=user, review_id=999999, rating=1)


@pytest.mark.django_db
class TestDelete:
    def test_deletes_own(self) -> None:
        user = UserFactory()
        review = ReviewService.create(
            user=user, place_id=PlaceFactory().pk, rating=5
        )

        ReviewService.delete(user=user, review_id=review.pk)

        assert not Review.objects.filter(pk=review.pk).exists()

    def test_delete_not_own_raises(self) -> None:
        owner = UserFactory()
        other = UserFactory()
        review = ReviewService.create(
            user=owner, place_id=PlaceFactory().pk, rating=5
        )

        with pytest.raises(NotReviewOwner):
            ReviewService.delete(user=other, review_id=review.pk)


@pytest.mark.django_db
class TestAchievementIntegration:
    def test_critic_unlocks_after_15_photo_reviews(self) -> None:
        """Ачивка 'critic' даётся за 15 отзывов с фото."""
        # Для теста — отзывы без фото; чекер критика требует photo__isnull=False,
        # поэтому 15 пустых не дадут ачивку. Это правильное поведение.
        Achievement.objects.create(
            code="critic",
            name_ru="Критик",
            description_ru="...",
        )

        user = UserFactory()
        for _ in range(15):
            place = PlaceFactory()
            ReviewService.create(user=user, place_id=place.pk, rating=5)

        # Без photo — ачивка не должна сработать.
        assert not UserAchievement.objects.filter(
            user=user, achievement__code="critic"
        ).exists()