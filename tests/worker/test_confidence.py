# Routing is allowed when either head is at or above its configured threshold.
# Routing is withheld only when both heads are below their thresholds.
# Read the thresholds from the config files so a change there moves the boundary.

import math
from pathlib import Path
from typing import cast

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


def test_zero_and_one_are_probabilities() -> None:
    withheld = evaluate(0, 0)
    assert withheld.category_confident is False
    assert withheld.priority_confident is False
    assert withheld.allow_routing is False

    routed = evaluate(1, 0)
    assert routed.category_confident is True
    assert routed.allow_routing is True


@pytest.mark.parametrize(
    ("category_confidence", "priority_confidence"),
    [(True, 0.5), (0.5, False), (float("nan"), 0.5), (0.5, float("inf"))],
)
def test_non_probabilities_are_rejected(
    category_confidence: object,
    priority_confidence: object,
) -> None:
    with pytest.raises(ConfidenceGateError):
        evaluate(cast(float, category_confidence), cast(float, priority_confidence))


def test_thresholds_come_from_the_config_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "confidence.yaml").write_text("threshold: 0.5\n", encoding="utf-8")
    (tmp_path / "priority_policy.yaml").write_text(
        "default: P3\nthreshold: 0.5\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))

    category_only = evaluate(0.5, 0.4)
    assert category_only.category_confident is True
    assert category_only.priority_confident is False
    assert category_only.allow_routing is True

    priority_only = evaluate(0.4, 0.5)
    assert priority_only.category_confident is False
    assert priority_only.priority_confident is True
    assert priority_only.allow_routing is True

    withheld = evaluate(0.4, 0.4)
    assert withheld.allow_routing is False


def test_a_missing_threshold_file_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    with pytest.raises(ConfidenceGateError, match="not found"):
        evaluate(0.5, 0.5)
