# The worker posts the decision to the webhook with an idempotency key.
# A second attempt with the same key does not create a second logical notification.
# A failed delivery is recorded and can be retried.
