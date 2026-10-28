# Background worker image.
# Build context is the repository root.
# This process claims queued tickets, classifies the category with the exported
# model, applies the priority and routing rules, stores the decision, and
# notifies the webhook.
# The training notebook is not part of this image.
# docker-compose.yml mounts ./models at /app/models and ./config at /app/config.

FROM python:3.12-slim

WORKDIR /app

COPY common/requirements.txt /tmp/common-requirements.txt
COPY common/desktriage_common /app/desktriage_common
COPY worker/requirements.txt /tmp/worker-requirements.txt
COPY worker /app/worker
COPY config /app/config

# Install both requirements files, including the library that loads the exported model.
# Set PYTHONPATH=/app so `import desktriage_common` and `import worker` resolve.
# Start the process in worker/app/main.py.
# Do not copy training/ into this image. Read the model from /app/models.
