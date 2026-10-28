# Persist a new ticket and read it back by its public id.
# Insert the ticket with status queued and return the id the assistant will poll.
# The status read returns the lifecycle value and, once the worker has finished,
# the stored decision. This module does not classify or route.
