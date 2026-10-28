# Intake API image.
# Build context is the repository root, as set in docker-compose.yml.
# This image stores an escalated ticket and serves its status.
# Classification, priority, routing, and notification belong to the worker image.

FROM python:3.12-slim

WORKDIR /app

COPY common/requirements.txt /tmp/common-requirements.txt
COPY common/desktriage_common /app/desktriage_common
COPY api/requirements.txt /tmp/api-requirements.txt
COPY api /app/api

# Install both requirements files.
# Set PYTHONPATH=/app so `import desktriage_common` and `import api` resolve.
# Start the process in api/app/main.py and listen on port 8000.
EXPOSE 8000
