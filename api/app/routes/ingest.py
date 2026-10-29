"""POST the intake route.

Validate the body, store the ticket, and return a structured response
with the ticket id and the accepted status. Return the error response
from api/app/errors.py when validation or storage fails.
"""

import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from common.desktriage_common.schemas import TicketAccepted

from ..errors import TicketStoreError, intake_error_response
from ..repository import insert_ticket
from ..validation import IntakeValidationError, validate_intake

router = APIRouter()


@router.post("/tickets", status_code=202, response_model=TicketAccepted)
async def intake(request: Request) -> TicketAccepted | JSONResponse:
    """Accept an escalated query.

    The response is the new ticket id and the accepted status. Category,
    priority, and assigned team are not included. The worker writes those
    later, and the assistant reads them from the status route.
    """
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return intake_error_response(IntakeValidationError("intake body is malformed"))

    try:
        ticket = validate_intake(body)
        return insert_ticket(ticket)
    except (IntakeValidationError, TicketStoreError) as exc:
        return intake_error_response(exc)
