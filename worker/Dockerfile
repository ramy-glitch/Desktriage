# Background worker image.
# Build context is the repository root, as set in docker-compose.yml.
# This process claims queued tickets, classifies them with the exported model,
# stores the decision, and notifies the webhook.
# The training notebook is not part of this image.
# The exported model is copied to /app/models and scored inside this process.
# docker-compose.yml mounts ./config at /app/config.

FROM python:3.12-slim

WORKDIR /app

COPY common/requirements.txt /tmp/common-requirements.txt
COPY worker/requirements.txt /tmp/worker-requirements.txt
RUN pip install --no-cache-dir -r /tmp/common-requirements.txt -r /tmp/worker-requirements.txt

COPY common/desktriage_common /app/desktriage_common
COPY worker /app/worker
COPY config /app/config
COPY models /app/models

# PYTHONPATH=/app makes `import desktriage_common` and `import worker` resolve.
# Do not copy training/ into this image.
ENV PYTHONPATH=/app
CMD ["python", "-m", "worker.app.main"]
