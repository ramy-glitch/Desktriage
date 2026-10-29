"""Create the application and register the routers in api/app/routes.

Read settings from desktriage_common.config.
On startup, confirm the database session from desktriage_common.db can be opened.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from common.desktriage_common.config import get_settings
from common.desktriage_common.db import check_session
from common.desktriage_common.logging import get_logger

from .routes.health import router as health_router
from .routes.ingest import router as ingest_router
from .routes.status import router as status_router

_logger = get_logger("api")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Read settings, then confirm PostgreSQL accepts a connection.

    A database error stops startup. The error text is left out of the log
    so a connection string is not recorded.
    """
    get_settings()
    try:
        check_session()
    except Exception as exc:
        _logger.error("event=startup_failure error_type=%s", type(exc).__name__)
        raise
    yield


def create_app() -> FastAPI:
    """Build the intake API and register its routers."""
    application = FastAPI(title="Desktriage", lifespan=lifespan)
    application.include_router(ingest_router)
    application.include_router(status_router)
    application.include_router(health_router)
    return application


app = create_app()


def main() -> None:
    """Listen on port 8000."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
