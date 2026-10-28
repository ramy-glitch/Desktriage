# The pipeline runs classification, priority, the confidence gate, then either
# human review or routing, then the decision write and the notification.
# A low-confidence ticket ends in review and is not given an automatic team.
# A high-confidence ticket ends routed to the configured team.
