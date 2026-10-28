# The status route returns the ticket id and the lifecycle status.
# Before the worker finishes, the decision fields are empty.
# After a stored decision, the response includes category, priority, confidence,
# the human-review flag, and the destination when one was assigned.
# An unknown id returns a not-found error.
