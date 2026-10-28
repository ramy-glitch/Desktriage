# Check an intake body against TicketIngest in desktriage_common.schemas.
# Reject a body that is missing the escalated query or is otherwise malformed.
# The assistant submits the query that needs triage. Category, priority, and
# assigned team are produced later by the worker.
