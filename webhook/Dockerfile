# Mock webhook image.
# This container stands in for the system that should hear when a ticket is ready.
# It records deliveries so you can see retries and duplicate keys.
# It is not the support team queue and it does not classify tickets.

FROM python:3.12-slim

WORKDIR /app

COPY common/requirements.txt /tmp/common-requirements.txt
COPY common/desktriage_common /app/desktriage_common
COPY webhook/requirements.txt /tmp/webhook-requirements.txt
COPY webhook /app/webhook

# Install both requirements files so the shared notification schema imports.
# Set PYTHONPATH=/app.
# Start webhook/app/main.py and listen on port 8001.
EXPOSE 8001
