"""Shapes shared across the intake API, the worker, and the webhook.

TicketIngest is the escalated query the assistant submits. It is not a labelled
dataset row: category, priority, and assigned team are worker outputs.

TicketAccepted is the ticket id and status returned immediately after intake.

TicketStatus is the ticket id, current lifecycle status, and the stored
decision once the worker has written one.

TriageDecision is the category, priority, confidence, human-review flag,
destination, and model version.

WebhookNotification is the decision payload the worker posts. The idempotency
key makes a retry the same notification delivered again.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from desktriage_common.enums import Category, Priority
from desktriage_common.statuses import Status


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _required_text(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be empty")
    return stripped


class TicketIngest(_Contract):
    """Escalated query submitted by the assistant."""

    query_text: str
    escalation_reason: str
    user_id: str 

    @field_validator("query_text", "escalation_reason", "user_id")
    @classmethod
    def text_must_be_present(cls, value: str) -> str:
        return _required_text(value)




class TriageDecision(_Contract):
    """Outcome stored for one finished triage attempt."""

    category: Category
    priority: Priority
    confidence: float = Field(ge=0.0, le=1.0)
    requires_human_review: bool
    destination: str | None = None
    model_version: str

    @field_validator("model_version")
    @classmethod
    def version_must_be_present(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("destination")
    @classmethod
    def destination_if_present(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _required_text(value)

    @model_validator(mode="after")
    def destination_follows_review(self) -> "TriageDecision":
        if self.requires_human_review and self.destination is not None:
            raise ValueError("a human-review decision has no destination team")
        if not self.requires_human_review and self.destination is None:
            raise ValueError("an automatically routed decision needs a destination team")
        return self


class TicketAccepted(_Contract):
    """Response the intake route returns as soon as the ticket is stored."""

    ticket_id: str
    status: Status = Status.ACCEPTED

    @field_validator("ticket_id")
    @classmethod
    def ticket_id_must_be_present(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("status")
    @classmethod
    def intake_returns_accepted(cls, value: Status) -> Status:
        if value is not Status.ACCEPTED:
            raise ValueError("intake returns the accepted status")
        return value


class TicketStatus(_Contract):
    """Ticket the assistant reads back by id."""

    ticket_id: str
    status: Status
    decision: TriageDecision | None = None

    @field_validator("ticket_id")
    @classmethod
    def ticket_id_must_be_present(cls, value: str) -> str:
        return _required_text(value)

    @model_validator(mode="after")
    def decision_follows_status(self) -> "TicketStatus":
        in_progress = {Status.ACCEPTED, Status.QUEUED, Status.PROCESSING}
        finished = {Status.ROUTED, Status.NEEDS_HUMAN_REVIEW}
        if self.status in in_progress and self.decision is not None:
            raise ValueError("a ticket still in progress has no stored decision")
        if self.status in finished and self.decision is None:
            raise ValueError("a completed triage status includes the stored decision")
        if self.decision is not None and self.status in finished:
            expected = (
                Status.NEEDS_HUMAN_REVIEW
                if self.decision.requires_human_review
                else Status.ROUTED
            )
            if self.status is not expected:
                raise ValueError("status does not match the stored decision")
        return self


class WebhookNotification(_Contract):
    """Decision payload posted to the webhook receiver."""

    idempotency_key: str
    ticket_id: str
    status: Status
    decision: TriageDecision

    @field_validator("idempotency_key", "ticket_id")
    @classmethod
    def identifiers_must_be_present(cls, value: str) -> str:
        return _required_text(value)

    @model_validator(mode="after")
    def status_matches_decision(self) -> "WebhookNotification":
        expected = (
            Status.NEEDS_HUMAN_REVIEW
            if self.decision.requires_human_review
            else Status.ROUTED
        )
        if self.status is not expected:
            raise ValueError("notification status does not match the decision")
        return self
