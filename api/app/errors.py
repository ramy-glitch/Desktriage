# Map intake failures to an HTTP response the caller can understand.
# Incomplete or malformed bodies get a validation error.
# A failure while storing a new ticket gets an error response, and the ticket
# is not left in an unrecorded state. Processing failures after a successful
# intake belong to the worker, which keeps the row and retries it.
