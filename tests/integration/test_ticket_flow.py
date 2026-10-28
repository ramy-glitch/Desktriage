# End-to-end check across the Compose services.
# Submit a valid ticket to the API and read it back by id.
# After the worker runs, the status includes the decision, and the webhook
# receiver has one logical notification for that decision.
# Also run one ticket that falls below the confidence threshold and confirm
# the status is human review and no destination team was assigned.
# Invalid bodies are covered in tests/api and can stay out of this stack test.
