# Decide whether a prediction may be routed automatically.
# Read the threshold from config/confidence.yaml. That number comes from the
# validation work in the training notebook.
# At or above the threshold, the pipeline may call routing.
# Below the threshold, the pipeline sends the ticket to human review.
