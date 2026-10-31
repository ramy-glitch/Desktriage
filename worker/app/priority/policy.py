"""Assign operational handling priority from config/priority_policy.yaml.

The dataset card defines P1 to P4 as administrative handling priority.
Return one priority value from desktriage_common.enums. The category model
does not choose this value. The training notebook is where you check this
policy against the labelled priorities.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

from desktriage_common.enums import Priority

_POLICY_FILENAME = "priority_policy.yaml"


class PriorityPolicyError(ValueError):
    """The priority policy file is missing or does not describe P1–P4 rules."""


@dataclass(frozen=True)
class _Policy:
    default: Priority
    rules: tuple[tuple[Priority, tuple[str, ...]], ...]


def assign_priority(query_text: str) -> Priority:
    """Return the first matching priority, or the policy default.

    A rule matches when query_text contains one of its phrases, ignoring case.
    Rules run in the order written in the file, so an earlier deadline cue
    wins over a later one. The current policy matches query_text only.
    """
    if not isinstance(query_text, str) or not query_text.strip():
        raise PriorityPolicyError("query_text must not be empty")

    policy = _load_policy(_policy_path())
    haystack = query_text.casefold()
    for priority, phrases in policy.rules:
        if any(phrase in haystack for phrase in phrases):
            return priority
    return policy.default


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

    default = _as_priority(loaded.get("default"), where="default")
    raw_rules = loaded.get("rules")
    if not isinstance(raw_rules, list):
        raise PriorityPolicyError("rules must be a list")

    rules: list[tuple[Priority, tuple[str, ...]]] = []
    for index, rule in enumerate(raw_rules, start=1):
        if not isinstance(rule, Mapping):
            raise PriorityPolicyError(f"rule {index} must be a mapping")
        priority = _as_priority(rule.get("priority"), where=f"rule {index} priority")
        phrases = _phrases(rule.get("query_text_contains_any"), index=index)
        rules.append((priority, phrases))
    return _Policy(default=default, rules=tuple(rules))


def _as_priority(value: object, *, where: str) -> Priority:
    if not isinstance(value, str):
        raise PriorityPolicyError(f"{where} must be P1, P2, P3, or P4")
    try:
        return Priority(value.strip())
    except ValueError as exc:
        raise PriorityPolicyError(f"{where} must be P1, P2, P3, or P4") from exc


def _phrases(value: object, *, index: int) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise PriorityPolicyError(f"rule {index} needs at least one query_text phrase")
    phrases: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise PriorityPolicyError(f"rule {index} has an empty query_text phrase")
        phrases.append(item.strip().casefold())
    return tuple(phrases)
