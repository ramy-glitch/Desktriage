# Shapes shared across the intake API, the worker, and the webhook.
#
# TicketIngest
#   The escalated query the assistant submits: query text, escalation reason,
#   and any identifiers the assistant already has. This is not a labelled dataset row.
#   Category, priority, and assigned team are worker outputs.
#
# TicketAccepted
#   Ticket id and the status the API returns immediately after intake.
#
# TicketStatus
#   Ticket id, current status, and the stored decision once the worker has written one.
#
# TriageDecision
#   Category, priority, confidence, human-review flag, destination, and model version.
#
# WebhookNotification
#   The decision payload the worker posts. Include an idempotency key so a retry
#   is the same notification delivered again.
