"""Check an intake body against TicketIngest.

Reject a body that is missing the escalated query or is otherwise malformed.
The assistant submits the query that needs triage. Category, priority, and
assigned team are produced later by the worker.
"""

from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from common.desktriage_common.schemas import TicketIngest


class IntakeValidationError(ValueError):
    """The intake body is missing the escalated query or is otherwise malformed.

    `errors` lists the schema mismatches without the submitted field values,
    so a caller can build an error response without logging ticket content.
    """

    def __init__(self, message: str, *, errors: list[dict[str, str]] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or []


def validate_intake(body: object) -> TicketIngest:
    """Return the parsed ticket, or raise IntakeValidationError.

    A body with no usable query_text is rejected as missing the escalated
    query. Any other mismatch with TicketIngest is rejected as malformed,
    including category, priority, or assigned team.
    """
    if not isinstance(body, Mapping):
        raise IntakeValidationError("intake body is malformed")

    try:
        return TicketIngest.model_validate(body)
    except ValidationError as exc:
        errors = _error_details(exc)
        if _query_is_missing(body):
            raise IntakeValidationError(
                "intake body is missing the escalated query",
                errors=errors,
            ) from exc
        raise IntakeValidationError("intake body is malformed", errors=errors) from exc


def _query_is_missing(body: Mapping[str, Any]) -> bool:
    if "query_text" not in body:
        return True
    value = body["query_text"]
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def _error_details(exc: ValidationError) -> list[dict[str, str]]:
    details: list[dict[str, str]] = []
    for err in exc.errors(include_url=False, include_context=False, include_input=False):
        field = ".".join(str(part) for part in err["loc"])
        details.append({"field": field, "message": err["msg"], "type": err["type"]})
    return details
