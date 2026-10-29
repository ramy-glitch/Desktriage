"""Operational logging for the API and the worker.

Record request failures, processing delays, retries, and routing outcomes.
Leave ticket query text and other ticket content out of the log messages.
Counts, latency, and error rates can be added here later; each helper already
emits a stable event name those metrics can count.
"""

import logging
import os
import sys

from desktriage_common.enums import Category, Priority
from desktriage_common.statuses import Status

LOGGER_NAME = "desktriage"


def configure_logging(level: str | None = None) -> None:
    """Attach one stdout handler to the desktriage logger.

    LOG_LEVEL overrides the default of INFO when level is omitted.
    A second call updates the level and does not add another handler.
    """
    resolved = (level or os.environ.get("LOG_LEVEL", "INFO")).upper()
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(resolved)
    logger.propagate = False
    if logger.handlers:
        logger.handlers[0].setLevel(resolved)
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(resolved)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    logger.addHandler(handler)


def get_logger(component: str) -> logging.Logger:
    """Return the logger for one API or worker component."""
    configure_logging()
    return logging.getLogger(f"{LOGGER_NAME}.{component}")


def log_request_failure(
    logger: logging.Logger,
    *,
    status_code: int,
    error_type: str,
    ticket_id: str | None = None,
) -> None:
    """Record an intake or status failure. error_type is an exception class name."""
    logger.error(
        "event=request_failure ticket_id=%s status_code=%s error_type=%s",
        ticket_id,
        status_code,
        error_type,
    )


def log_processing_delay(
    logger: logging.Logger,
    *,
    ticket_id: str,
    elapsed_ms: float,
) -> None:
    """Record that handling a ticket took elapsed_ms."""
    logger.warning(
        "event=processing_delay ticket_id=%s elapsed_ms=%.0f",
        ticket_id,
        elapsed_ms,
    )


def log_retry(
    logger: logging.Logger,
    *,
    ticket_id: str,
    attempt: int,
    error_type: str,
) -> None:
    """Record a worker retry. error_type is an exception class name."""
    logger.warning(
        "event=retry ticket_id=%s attempt=%s error_type=%s",
        ticket_id,
        attempt,
        error_type,
    )


def log_routing_outcome(
    logger: logging.Logger,
    *,
    ticket_id: str,
    status: Status,
    category: Category,
    priority: Priority,
    destination: str | None,
    confidence: float,
) -> None:
    """Record where a finished ticket was sent."""
    logger.info(
        "event=routing_outcome ticket_id=%s status=%s category=%s priority=%s destination=%s confidence=%.3f",
        ticket_id,
        status.value,
        category.value,
        priority.value,
        destination,
        confidence,
    )
