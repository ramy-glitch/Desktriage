# Ticket lifecycle stored in PostgreSQL and returned by the status route.
#
# accepted -> queued -> processing -> routed
#                                 -> needs_human_review
#                                 -> failed
#
# `failed` means the worker could not finish. The ticket row stays in the database
# so the attempt can be retried. The API uses these values when the assistant
# reads a ticket back.
