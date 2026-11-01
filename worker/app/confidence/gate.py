"""Decide whether a prediction may be routed automatically.

Category confidence is compared with config/confidence.yaml.
Priority confidence is compared with the threshold in config/priority_policy.yaml.
Both numbers come from the validation sweep: the lowest candidate from 0.30
to 0.90 whose accepted-prediction error was at most 0.10.

Routing may proceed when either head is at or above its threshold.
The pipeline sends the ticket to human review only when both are below.
This module does not choose a team or replace a low-confidence priority.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

_CATEGORY_FILENAME = "confidence.yaml"
_PRIORITY_FILENAME = "priority_policy.yaml"


class ConfidenceGateError(ValueError):
    """A confidence threshold file is missing or a score is not a probability."""


@dataclass(frozen=True)
class _Thresholds:
    category: float
    priority: float


@dataclass(frozen=True)
class GateDecision:
    """Which heads cleared their thresholds, and whether routing may proceed."""

    category_confident: bool
    priority_confident: bool
    allow_routing: bool


def evaluate(category_confidence: float, priority_confidence: float) -> GateDecision:
    """Allow routing when either head is at or above its threshold."""
    category_confidence = _as_confidence(category_confidence, "category confidence")
    priority_confidence = _as_confidence(priority_confidence, "priority confidence")
    thresholds = _load_thresholds(_config_dir())
    category_confident = category_confidence >= thresholds.category
    priority_confident = priority_confidence >= thresholds.priority
    return GateDecision(
        category_confident=category_confident,
        priority_confident=priority_confident,
        allow_routing=category_confident or priority_confident,
    )


def _config_dir() -> Path:
    """Resolve the config directory from CONFIG_DIR, or from the repository config directory."""
    configured = os.environ.get("CONFIG_DIR", "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3] / "config"


def _load_thresholds(directory: Path) -> _Thresholds:
    category = _threshold(_read_yaml(directory / _CATEGORY_FILENAME), "confidence.yaml")
    priority = _threshold(_read_yaml(directory / _PRIORITY_FILENAME), "priority_policy.yaml")
    return _Thresholds(category=category, priority=priority)


def _read_yaml(path: Path) -> Mapping[str, object]:
    if not path.is_file():
        raise ConfidenceGateError(f"confidence file not found: {path}")
    with path.open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, Mapping):
        raise ConfidenceGateError(f"{path.name} must be a mapping")
    return loaded


def _threshold(loaded: Mapping[str, object], filename: str) -> float:
    return _as_unit(loaded.get("threshold"), f"{filename} threshold")


def _as_confidence(value: object, where: str) -> float:
    return _as_unit(value, where)


def _as_unit(value: object, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfidenceGateError(f"{where} must be a number from 0 to 1")
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise ConfidenceGateError(f"{where} must be a number from 0 to 1")
    return number
