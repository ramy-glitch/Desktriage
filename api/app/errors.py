"""Map intake failures to an HTTP response the caller can understand.

Incomplete or malformed bodies get a validation error.
A failure while storing a new ticket gets an error response, and the ticket
is not left in an unrecorded state. Processing failures after a successful
intake belong to the worker, which keeps the row and retries it.
"""

from fastapi.responses import JSONResponse

from desktriage_common.logging import get_logger, log_request_failure

from .validation import IntakeValidationError

_logger = get_logger("api")


class TicketStoreError(Exception):
    """The insert did not commit, so no ticket row was left behind.

    Raise this from the intake route after the database session has rolled
    back. The worker must not see a row for an intake that failed.
    """


def validation_error_response(exc: IntakeValidationError) -> JSONResponse:
    """422 when the body is missing the escalated query or is otherwise malformed."""
    log_request_failure(
        _logger,
        status_code=422,
        error_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "message": str(exc),
            "errors": exc.errors,
        },
    )


def storage_error_response(exc: TicketStoreError) -> JSONResponse:
    """500 when storing a new ticket fails.

    The body has no ticket id. The session rollback means the worker cannot
    claim a row that was never recorded. The original exception text stays
    out of the response so query text cannot leak through a database error.
    """
    cause = exc.__cause__ or exc
    log_request_failure(
        _logger,
        status_code=500,
        error_type=type(cause).__name__,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "storage_error",
            "message": "the ticket was not stored",
        },
    )


def not_found_response(ticket_id: str) -> JSONResponse:
    """404 when the status route is asked for an id that is not stored."""
    log_request_failure(
        _logger,
        status_code=404,
        error_type="TicketNotFound",
        ticket_id=ticket_id,
    )
    return JSONResponse(
        status_code=404,
        content={
            "error": "not_found",
            "message": "ticket not found",
            "ticket_id": ticket_id,
        },
    )


def intake_error_response(exc: IntakeValidationError | TicketStoreError) -> JSONResponse:
    """Return the response for a validation failure or a failed insert.

    A failure after the ticket is stored is handled by the worker. Passing
    any other exception here is rejected so that case is not reported as
    an unrecorded ticket.
    """
    if isinstance(exc, IntakeValidationError):
        return validation_error_response(exc)
    if isinstance(exc, TicketStoreError):
        return storage_error_response(exc)
    raise TypeError("intake_error_response handles validation and storage failures only")
