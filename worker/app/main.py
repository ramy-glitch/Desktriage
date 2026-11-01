"""Process entrypoint for the worker container.

Load settings, open the database, load the exported category model once,
and run the poll loop until the process stops.
"""

import signal
from threading import Event

from desktriage_common.config import get_settings
from desktriage_common.db import check_session
from desktriage_common.logging import get_logger

from worker.app.classifier.loader import load_classifier
from worker.app.loop import run

logger = get_logger("worker")


def main() -> None:
    """Start the worker and poll until the process is asked to stop.

    A database or model error stops startup. The log records the exception
    type and leaves the connection string and ticket text out.
    """
    stop = Event()
    _install_stop(stop)
    get_settings()
    try:
        check_session()
        load_classifier()
    except Exception as exc:
        logger.error("event=startup_failure error_type=%s", type(exc).__name__)
        raise
    logger.info("event=worker_started")
    run(stop=stop.is_set)
    logger.info("event=worker_stopped")


def _install_stop(stop: Event) -> None:
    """Ask the poll loop to return when the process receives SIGINT or SIGTERM."""

    def request_stop(signum: int, _frame: object) -> None:
        logger.info("event=shutdown_requested signal=%s", signum)
        stop.set()

    for name in ("SIGINT", "SIGTERM"):
        signum = getattr(signal, name, None)
        if isinstance(signum, int):
            signal.signal(signum, request_stop)


if __name__ == "__main__":
    main()
