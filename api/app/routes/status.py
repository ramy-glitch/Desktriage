"""GET the status route used by the Deskline assistant.

Look up the ticket id through api/app/repository.py.
Return the current status. Include category, priority, confidence,
human-review flag, and destination after the worker has recorded them.
Return a not-found error for an unknown id.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from desktriage_common.schemas import TicketStatus

from ..errors import not_found_response
from ..repository import get_ticket

router = APIRouter()


@router.get("/tickets/{ticket_id}", response_model=TicketStatus)
def ticket_status(ticket_id: str) -> TicketStatus | JSONResponse:
    """Return the lifecycle status for one ticket.

    Before the worker finishes, decision is empty. After a stored decision,
    the response includes category, priority, confidence, the human-review
    flag, and the destination when one was assigned.
    """
    ticket = get_ticket(ticket_id)
    if ticket is None:
        return not_found_response(ticket_id)
    return ticket
