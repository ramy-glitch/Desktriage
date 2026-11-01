"""Build the idempotency key for one stored decision.

The key is the ticket id and the triage_decisions id. A retry of that outcome
repeats the same key. A later decision for the same ticket gets a new key.
"""


class IdempotencyError(ValueError):
    """The ticket id or decision id cannot identify one notification."""


def decision_key(ticket_id: str, decision_id: int) -> str:
    """Return the key for one stored decision."""
    if not isinstance(ticket_id, str) or not ticket_id.strip():
        raise IdempotencyError("ticket_id must not be empty")
    if isinstance(decision_id, bool) or not isinstance(decision_id, int) or decision_id < 1:
        raise IdempotencyError("decision_id must be a positive integer")
    return f"{ticket_id.strip()}:{decision_id}"
