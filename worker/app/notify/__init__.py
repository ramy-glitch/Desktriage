# Tell the webhook receiver that a ticket has a stored outcome.
# webhook.py sends the HTTP request. idempotency.py builds the key that makes
# a retry the same notification.
