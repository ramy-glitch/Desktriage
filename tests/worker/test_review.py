# A below-threshold ticket is stored as needs_human_review.
# The decision still contains category, priority, and confidence.
# The destination team is empty.

import pytest

from desktriage_common.enums import Category, Priority
from desktriage_common.statuses import Status
from worker.app.review.queue import ReviewQueueError, hold_for_review


def test_withheld_ticket_has_no_team() -> None:
    review = hold_for_review(
        Category.COVERAGE_AND_BENEFITS,
        Priority.P2,
        0.2,
    )
    assert review.status is Status.NEEDS_HUMAN_REVIEW
    assert review.requires_human_review is True
    assert review.destination is None
    assert review.category is Category.COVERAGE_AND_BENEFITS
    assert review.priority is Priority.P2
    assert review.confidence == 0.2


def test_label_strings_are_accepted() -> None:
    review = hold_for_review("other_or_unknown", "P3", 0)
    assert review.category is Category.OTHER_OR_UNKNOWN
    assert review.priority is Priority.P3
    assert review.destination is None


def test_unknown_category_is_rejected() -> None:
    with pytest.raises(ReviewQueueError):
        hold_for_review("not_a_category", Priority.P3, 0.2)


def test_confidence_outside_zero_to_one_is_rejected() -> None:
    with pytest.raises(ReviewQueueError):
        hold_for_review(Category.ACCESS_AND_REFERRALS, Priority.P4, 1.1)


def test_confidence_of_one_is_kept() -> None:
    review = hold_for_review(Category.ACCESS_AND_REFERRALS, " P4 ", 1)
    assert review.priority is Priority.P4
    assert review.confidence == 1.0
    assert review.requires_human_review is True
    assert review.destination is None


def test_a_boolean_confidence_is_rejected() -> None:
    with pytest.raises(ReviewQueueError):
        hold_for_review(Category.ACCESS_AND_REFERRALS, Priority.P4, True)


def test_an_unknown_priority_is_rejected() -> None:
    with pytest.raises(ReviewQueueError):
        hold_for_review(Category.ACCESS_AND_REFERRALS, "p4", 0.4)


def test_a_negative_confidence_is_rejected() -> None:
    with pytest.raises(ReviewQueueError):
        hold_for_review(Category.ACCESS_AND_REFERRALS, Priority.P4, -0.01)
