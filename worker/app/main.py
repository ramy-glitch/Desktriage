# Process entrypoint for the worker container.
# Load settings, open the database, load the exported category model once,
# and run the poll loop until the process stops.
