# Remember notifications received by this local mock.
# Store the body and the idempotency key.
# A second POST with the same key is a duplicate delivery, not a second ticket.
# An in-memory store is enough for local verification. Log the receipt without
# writing the ticket query text.
