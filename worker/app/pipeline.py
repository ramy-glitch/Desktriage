# Run one claimed ticket through triage, in this order:
#   1. classifier.predict  -> category and confidence
#   2. priority.policy     -> operational priority
#   3. confidence.gate     -> whether the prediction is safe to route automatically
#   4. review.queue        -> human review when the gate withholds automatic routing
#      or routing.rules    -> destination team when the gate allows it
#   5. trace               -> store the decision
#   6. notify.webhook      -> tell the receiver the ticket is ready
# This module calls those steps. The rules themselves stay in their own modules.
# On an exception, call retry.py and leave the ticket in the database.
