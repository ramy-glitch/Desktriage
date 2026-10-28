# Build the idempotency key for one stored decision.
# Use the ticket id and the decision id so a retry of the same outcome
# repeats one notification. A later decision for the same ticket gets a new key.
