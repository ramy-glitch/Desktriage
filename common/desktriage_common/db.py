# Database session for the API and the worker.
# The schema itself lives in db/init and is applied by the PostgreSQL container.
# Open a session, commit a successful unit of work, and roll back on failure
# so a crashed request does not leave a half-written ticket.
