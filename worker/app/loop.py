# Poll for queued work.
# Call claim.py for one ticket, pass it to pipeline.py, then wait before polling again.
# When a ticket fails, leave it recorded and let retry.py decide when it is eligible again.
