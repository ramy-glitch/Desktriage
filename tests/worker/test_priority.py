# The priority policy returns the classifier priority head.
# Below the threshold in config/priority_policy.yaml, the priority is the default P3.
# At or above the threshold, the returned priority is the head's priority.

from pathlib import Path

import pytest
import yaml

from desktriage_common.enums import Category, Priority
from worker.app.classifier.predict import Classification
from worker.app.priority.policy import PriorityPolicyError, assign_priority


def _scored(priority: Priority, priority_confidence: float) -> Classification:
    return Classification(
        category=Category.OTHER_OR_UNKNOWN,
        confidence=0.9,
        priority=priority,
        priority_confidence=priority_confidence,
    )


def test_policy_file_keeps_the_validation_threshold() -> None:
    path = Path(__file__).resolve().parents[2] / "config" / "priority_policy.yaml"
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert loaded["default"] == "P3"
    assert loaded["threshold"] == 0.30


@pytest.mark.parametrize("priority", [Priority.P1, Priority.P2, Priority.P3, Priority.P4])
def test_confidence_at_or_above_the_threshold_keeps_the_head(
    monkeypatch: pytest.MonkeyPatch,
    priority: Priority,
) -> None:
    monkeypatch.setattr(
        "worker.app.priority.policy.predict",
        lambda query_text, escalation_reason: _scored(priority, 0.30),
    )
    assert assign_priority("a query", "a reason") is priority


@pytest.mark.parametrize("priority", [Priority.P1, Priority.P2, Priority.P4])
def test_confidence_below_the_threshold_is_p3(
    monkeypatch: pytest.MonkeyPatch,
    priority: Priority,
) -> None:
    monkeypatch.setattr(
        "worker.app.priority.policy.predict",
        lambda query_text, escalation_reason: _scored(priority, 0.29),
    )
    assert assign_priority("a query", "a reason") is Priority.P3


@pytest.mark.parametrize(
    ("query_text", "escalation_reason"),
    [("   ", "the assistant could not answer"), ("a query", "  ")],
)
def test_blank_text_is_rejected(query_text: str, escalation_reason: str) -> None:
    with pytest.raises(PriorityPolicyError):
        assign_priority(query_text, escalation_reason)
