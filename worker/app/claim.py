# Take one queued ticket so this worker is the only one processing it.
# Use a row lock (for example SELECT ... FOR UPDATE SKIP LOCKED) so another
# worker container skips a ticket that is already claimed.
# Move the ticket to processing and record which attempt this is.
