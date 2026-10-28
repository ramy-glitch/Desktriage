# Read runtime settings from the environment.
# DATABASE_URL is how the API and the worker reach PostgreSQL.
# WEBHOOK_URL is how the worker reaches the notification receiver.
# Paths inside the worker container:
#   /app/config  routing rules, priority policy, confidence threshold
#   /app/models  exported category classifier
