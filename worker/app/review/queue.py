"""Hold a ticket for human review.

The status is needs_human_review and the destination team stays unset.
Category, priority, and confidence stay on the result so a reviewer can see
why automatic routing was withheld. The status route reads that result back
after trace.py stores it. This module does not choose a team.
"""

from dataclasses import dataclass

from desktriage_common.enums import Category, Priority
from desktriage_common.statuses import Status


class ReviewQueueError(ValueError):
    """The review record is missing a label or its confidence is not a probability."""


@dataclass(frozen=True)
class HumanReview:
    """One withheld ticket, with the scores a reviewer needs and no team."""

    category: Category
    priority: Priority
    confidence: float
    status: Status = Status.NEEDS_HUMAN_REVIEW
    requires_human_review: bool = True
    destination: str | None = None


def hold_for_review(
    category: Category | str,
    priority: Priority | str,
    confidence: float,
) -> HumanReview:
    """Mark one ticket for human review and leave the destination unset."""
    return HumanReview(
        category=_as_category(category),
        priority=_as_priority(priority),
        confidence=_as_confidence(confidence),
    )


def _as_category(value: object) -> Category:
    if isinstance(value, Category):
        return value
    if isinstance(value, str):
        try:
            return Category(value.strip())
        except ValueError as exc:
            raise ReviewQueueError(f"unknown category: {value.strip()}") from exc
    raise ReviewQueueError("category must be one of the shared category labels")


def _as_priority(value: object) -> Priority:
    if isinstance(value, Priority):
        return value
    if isinstance(value, str):
        try:
            return Priority(value.strip())
        except ValueError as exc:
            raise ReviewQueueError("priority must be P1, P2, P3, or P4") from exc
    raise ReviewQueueError("priority must be P1, P2, P3, or P4")


def _as_confidence(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReviewQueueError("confidence must be a number from 0 to 1")
    confidence = float(value)
    if not 0.0 <= confidence <= 1.0:
        raise ReviewQueueError("confidence must be a number from 0 to 1")
    return confidence
