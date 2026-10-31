# Run the exported two-head model on query text and escalation reason.
# Return the category, the category-head confidence, and the priority.
# Confidence for the gate is the maximum probability of the category head.
# Use the label names from desktriage_common.enums.
# This function does not choose a team or decide human review.
