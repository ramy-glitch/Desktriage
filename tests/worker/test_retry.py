# A processing failure keeps the ticket row, increments the attempt, and
# schedules another claim.
# Past the attempt limit, the status becomes failed and the ticket remains readable.
