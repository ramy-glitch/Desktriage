"""GET the health route.

Report that this process is running and that PostgreSQL accepts a connection.
Compose can call this once you want the API to gate dependent startup.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from common.desktriage_common.db import check_session
from common.desktriage_common.logging import get_logger, log_request_failure

router = APIRouter()
_logger = get_logger("api")


@router.get("/health")
def health() -> JSONResponse:
    """Report that this process is running and whether PostgreSQL answered.

    A caller that cannot use the API yet receives 503. The database error
    text stays out of the response.
    """
    try:
        check_session()
    except Exception as exc:
        log_request_failure(
            _logger,
            status_code=503,
            error_type=type(exc).__name__,
        )
        return JSONResponse(
            status_code=503,
            content={"status": "ok", "database": "unavailable"},
        )
    return JSONResponse(status_code=200, content={"status": "ok", "database": "ok"})
