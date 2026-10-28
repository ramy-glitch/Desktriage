# Process entrypoint for the webhook container.
# Accept POST /notifications.
# Read the body as a WebhookNotification and pass it to receipts.py.
# Return success for a new delivery and for a repeated idempotency key.
