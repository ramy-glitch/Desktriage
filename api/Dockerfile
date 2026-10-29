# Intake API image.
# Build context is the repository root, as set in docker-compose.yml.
# This image stores an escalated ticket and serves its status.
# Classification, priority, routing, and notification belong to the worker image.

FROM python:3.12-slim

WORKDIR /app

COPY common/requirements.txt /tmp/common-requirements.txt
COPY api/requirements.txt /tmp/api-requirements.txt
RUN pip install --no-cache-dir -r /tmp/common-requirements.txt -r /tmp/api-requirements.txt

COPY common/desktriage_common /app/desktriage_common
COPY api /app/api

# PYTHONPATH=/app makes `import desktriage_common` and `import api` resolve.
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["python", "-m", "api.app.main"]
