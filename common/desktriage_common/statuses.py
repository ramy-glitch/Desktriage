"""Ticket lifecycle stored in PostgreSQL and returned by the status route.

accepted -> queued -> processing -> routed
                                -> needs_human_review
                                -> failed

`failed` means the worker could not finish. The ticket row stays in the database
so the attempt can be retried. The API uses these values when the assistant
reads a ticket back.
"""

from enum import StrEnum


class Status(StrEnum):
    """Lifecycle state of a ticket from intake through a stored decision."""

    ACCEPTED = "accepted"
    QUEUED = "queued"
    PROCESSING = "processing"
    ROUTED = "routed"
    NEEDS_HUMAN_REVIEW = "needs_human_review"
    FAILED = "failed"
