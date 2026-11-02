# Operational logs name the event, the ticket id, and the error type.
# Query text is not one of the fields those helpers accept.

import logging

from desktriage_common.enums import Category, Priority
from desktriage_common.logging import (
    configure_logging,
    get_logger,
    log_processing_delay,
    log_request_failure,
    log_retry,
    log_routing_outcome,
)
from desktriage_common.statuses import Status


def test_configure_logging_keeps_a_single_handler() -> None:
    configure_logging("DEBUG")
    configure_logging("ERROR")
    logger = logging.getLogger("desktriage")
    try:
        assert len(logger.handlers) == 1
        assert logger.level == logging.ERROR
        assert logger.handlers[0].level == logging.ERROR
        assert logger.propagate is False
    finally:
        configure_logging("INFO")


def test_operational_events_name_the_outcome() -> None:
    records: list[str] = []

    class _Handler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record.getMessage())

    logger = get_logger("tests.logging")
    handler = _Handler()
    logger.addHandler(handler)
    try:
        log_request_failure(
            logger,
            status_code=422,
            error_type="IntakeValidationError",
            ticket_id="ticket-1",
        )
        log_processing_delay(logger, ticket_id="ticket-1", elapsed_ms=12.4)
        log_retry(logger, ticket_id="ticket-1", attempt=2, error_type="TimeoutError")
        log_routing_outcome(
            logger,
            ticket_id="ticket-1",
            status=Status.ROUTED,
            category=Category.CLAIMS_AND_APPEALS,
            priority=Priority.P2,
            destination="claims_support",
            confidence=0.8,
        )
    finally:
        logger.removeHandler(handler)

    text = "\n".join(records)
    assert "event=request_failure" in text
    assert "status_code=422" in text
    assert "event=processing_delay" in text
    assert "elapsed_ms=12" in text
    assert "event=retry" in text
    assert "attempt=2" in text
    assert "event=routing_outcome" in text
    assert "destination=claims_support" in text
    assert "query_text" not in text
