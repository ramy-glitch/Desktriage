# Mock webhook image.
# Build context is the repository root, as set in docker-compose.yml.
# This container stands in for the system that should hear when a ticket is ready.
# It records deliveries so you can see retries and duplicate keys.
# It is not the support team queue and it does not classify tickets.

FROM python:3.12-slim

WORKDIR /app

COPY common/requirements.txt /tmp/common-requirements.txt
COPY webhook/requirements.txt /tmp/webhook-requirements.txt
RUN pip install --no-cache-dir -r /tmp/common-requirements.txt -r /tmp/webhook-requirements.txt

COPY common/desktriage_common /app/desktriage_common
COPY webhook /app/webhook

# PYTHONPATH=/app makes `import desktriage_common` and `import webhook` resolve.
ENV PYTHONPATH=/app
EXPOSE 8001
CMD ["python", "-m", "webhook.app.main"]
