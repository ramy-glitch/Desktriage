# Intake failures return a meaningful error and do not leave an unrecorded ticket
# that the worker could silently skip.
# A ticket that was stored and later fails in the worker stays readable, with a
# failed or retrying status, rather than disappearing from the status route.
