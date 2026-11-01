# Routing is allowed when either head is at or above its configured threshold.
# Routing is withheld only when both heads are below their thresholds.
# Read the thresholds from the config files so a change there moves the boundary.

import math
from pathlib import Path

import pytest
import yaml

from worker.app.confidence.gate import ConfidenceGateError, evaluate


def _thresholds() -> tuple[float, float]:
    config = Path(__file__).resolve().parents[2] / "config"
    category = yaml.safe_load((config / "confidence.yaml").read_text(encoding="utf-8"))
    priority = yaml.safe_load((config / "priority_policy.yaml").read_text(encoding="utf-8"))
    return float(category["threshold"]), float(priority["threshold"])


def _just_below(threshold: float) -> float:
    return math.nextafter(threshold, -1.0)


def test_both_heads_at_their_thresholds_may_route() -> None:
    category_threshold, priority_threshold = _thresholds()
    decision = evaluate(category_threshold, priority_threshold)
    assert decision.category_confident is True
    assert decision.priority_confident is True
    assert decision.allow_routing is True


def test_category_alone_may_route() -> None:
    category_threshold, priority_threshold = _thresholds()
    decision = evaluate(category_threshold, _just_below(priority_threshold))
    assert decision.category_confident is True
    assert decision.priority_confident is False
    assert decision.allow_routing is True


def test_priority_alone_may_route() -> None:
    category_threshold, priority_threshold = _thresholds()
    decision = evaluate(_just_below(category_threshold), priority_threshold)
    assert decision.category_confident is False
    assert decision.priority_confident is True
    assert decision.allow_routing is True


def test_both_heads_below_their_thresholds_are_withheld() -> None:
    category_threshold, priority_threshold = _thresholds()
    decision = evaluate(_just_below(category_threshold), _just_below(priority_threshold))
    assert decision.allow_routing is False


def test_confidence_outside_zero_to_one_is_rejected() -> None:
    with pytest.raises(ConfidenceGateError):
        evaluate(1.1, 0.5)
    with pytest.raises(ConfidenceGateError):
        evaluate(0.5, -0.1)
