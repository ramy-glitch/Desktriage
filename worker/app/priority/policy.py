"""Assign operational priority from the classifier priority head.

The dataset card defines P1 to P4 as administrative handling priority.
Return one priority value from desktriage_common.enums.

config/priority_policy.yaml holds the confidence threshold and the default.
Confidence is the maximum probability of the priority head. At or above the
threshold, return that priority. Below it, return the default, which is P3.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

from desktriage_common.enums import Priority
from worker.app.classifier.predict import predict

_POLICY_FILENAME = "priority_policy.yaml"


class PriorityPolicyError(ValueError):
    """The priority policy file is missing or does not describe a threshold and default."""


@dataclass(frozen=True)
class _Policy:
    default: Priority
    threshold: float


def assign_priority(query_text: str, escalation_reason: str) -> Priority:
    """Return the priority head, or the default when its confidence is below the threshold."""
    if not isinstance(query_text, str) or not query_text.strip():
        raise PriorityPolicyError("query_text must not be empty")
    if not isinstance(escalation_reason, str) or not escalation_reason.strip():
        raise PriorityPolicyError("escalation_reason must not be empty")

    policy = _load_policy(_policy_path())
    scored = predict(query_text, escalation_reason)
    if scored.priority_confidence < policy.threshold:
        return policy.default
    return scored.priority


def _policy_path() -> Path:
    """Resolve priority_policy.yaml from CONFIG_DIR, or from the repository config directory."""
    configured = os.environ.get("CONFIG_DIR", "").strip()
    if configured:
        return Path(configured) / _POLICY_FILENAME
    return Path(__file__).resolve().parents[3] / "config" / _POLICY_FILENAME


def _load_policy(path: Path) -> _Policy:
    if not path.is_file():
        raise PriorityPolicyError(f"priority policy file not found: {path}")
    with path.open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, Mapping):
        raise PriorityPolicyError("priority policy must be a mapping")
    return _Policy(
        default=_as_priority(loaded.get("default"), where="default"),
        threshold=_as_threshold(loaded.get("threshold")),
    )


def _as_priority(value: object, *, where: str) -> Priority:
    if not isinstance(value, str):
        raise PriorityPolicyError(f"{where} must be P1, P2, P3, or P4")
    try:
        return Priority(value.strip())
    except ValueError as exc:
        raise PriorityPolicyError(f"{where} must be P1, P2, P3, or P4") from exc


def _as_threshold(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PriorityPolicyError("threshold must be a number from 0 to 1")
    threshold = float(value)
    if not 0.0 <= threshold <= 1.0:
        raise PriorityPolicyError("threshold must be a number from 0 to 1")
    return threshold
