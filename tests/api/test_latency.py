# Measure intake latency against the target you document.
# State the target in the test once you have chosen it.
# This is the API timing check from the acceptance criteria. Model quality stays
# in the training notebook.

import statistics
import time

import pytest
from fastapi.testclient import TestClient

from desktriage_common.schemas import TicketAccepted

# Intake validates and stores the ticket, then returns. Classification runs in
# the worker, so this bound is the acknowledgement, measured here with the
# insert replaced by a stand-in. Five local calls, median under one second.
INTAKE_LATENCY_TARGET_SECONDS = 1.0


def test_intake_acknowledgement_meets_the_latency_target(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    intake_body: dict[str, str],
) -> None:
    monkeypatch.setattr(
        "api.app.routes.ingest.insert_ticket",
        lambda ticket: TicketAccepted(ticket_id="ticket-1"),
    )
    api_client.post("/tickets", json=intake_body)

    samples: list[float] = []
    for _ in range(5):
        started = time.perf_counter()
        response = api_client.post("/tickets", json=intake_body)
        samples.append(time.perf_counter() - started)
        assert response.status_code == 202

    assert statistics.median(samples) < INTAKE_LATENCY_TARGET_SECONDS
