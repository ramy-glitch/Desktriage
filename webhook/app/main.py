"""Process entrypoint for the webhook container.

Accept POST /notifications. Read the body as a WebhookNotification and pass it
to receipts.py. Return success for a new delivery and for a repeated
idempotency key.
"""

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict

from desktriage_common.schemas import WebhookNotification

from .receipts import remember

_IDEMPOTENCY_HEADER = "Idempotency-Key"


class NotificationReceipt(BaseModel):
    """Acknowledgement returned to the worker."""

    model_config = ConfigDict(extra="forbid")

    idempotency_key: str
    ticket_id: str
    duplicate: bool


def create_app() -> FastAPI:
    """Build the local receiver."""
    application = FastAPI(title="Desktriage webhook")

    @application.post(
        "/notifications",
        status_code=200,
        response_model=NotificationReceipt,
    )
    def receive(
        notification: WebhookNotification,
        idempotency_key: str | None = Header(default=None, alias=_IDEMPOTENCY_HEADER),
    ) -> NotificationReceipt:
        """Accept one stored decision.

        A repeated key returns success and leaves the first stored body in place.
        When the Idempotency-Key header is present, it has to match the body.
        """
        if idempotency_key is not None and idempotency_key.strip() != notification.idempotency_key:
            raise HTTPException(status_code=400, detail="idempotency key does not match the body")
        receipt = remember(notification)
        return NotificationReceipt(
            idempotency_key=receipt.idempotency_key,
            ticket_id=receipt.ticket_id,
            duplicate=receipt.duplicate,
        )

    return application


app = create_app()


def main() -> None:
    """Listen on port 8001."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)


if __name__ == "__main__":
    main()
