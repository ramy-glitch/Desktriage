"""Map category to a destination team using config/routing_rules.yaml.

Call this only when confidence.gate allows automatic routing.
Return the team that trace.py stores and the webhook payload reports.
A category listed for human review returns None, so the destination stays unset.
Align the destinations with the dataset's assigned_team labels.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

from desktriage_common.enums import Category, Priority

_RULES_FILENAME = "routing_rules.yaml"


class RoutingRulesError(ValueError):
    """The routing file is missing or does not cover the shared categories."""


@dataclass(frozen=True)
class _Routes:
    teams: Mapping[Category, str]
    human_review: frozenset[Category]


def destination_team(category: Category | str) -> str | None:
    resolved_category = _as_category(category)
    routes = _load_rules(_rules_path())
    if resolved_category in routes.human_review:
        return None
    return routes.teams[resolved_category]


def _rules_path() -> Path:
    """Resolve routing_rules.yaml from CONFIG_DIR, or from the repository config directory."""
    configured = os.environ.get("CONFIG_DIR", "").strip()
    if configured:
        return Path(configured) / _RULES_FILENAME
    return Path(__file__).resolve().parents[3] / "config" / _RULES_FILENAME


def _load_rules(path: Path) -> _Routes:
    if not path.is_file():
        raise RoutingRulesError(f"routing rules file not found: {path}")
    with path.open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, Mapping):
        raise RoutingRulesError("routing rules must be a mapping")

    teams = _teams(loaded.get("routes"))
    human_review = _human_review(loaded.get("human_review_categories"))
    overlap = human_review.intersection(teams)
    if overlap:
        names = ", ".join(sorted(category.value for category in overlap))
        raise RoutingRulesError(f"categories cannot be both routed and held for review: {names}")
    missing = set(Category) - set(teams) - human_review
    if missing:
        names = ", ".join(sorted(category.value for category in missing))
        raise RoutingRulesError(f"routing rules do not cover: {names}")
    return _Routes(teams=teams, human_review=human_review)


def _teams(value: object) -> dict[Category, str]:
    if not isinstance(value, Mapping):
        raise RoutingRulesError("routes must be a mapping of category to team")
    teams: dict[Category, str] = {}
    for raw_category, raw_team in value.items():
        category = _as_category(raw_category)
        if not isinstance(raw_team, str) or not raw_team.strip():
            raise RoutingRulesError(f"{category.value} needs a destination team")
        teams[category] = raw_team.strip()
    return teams


def _human_review(value: object) -> frozenset[Category]:
    if not isinstance(value, list):
        raise RoutingRulesError("human_review_categories must be a list")
    return frozenset(_as_category(item) for item in value)


def _as_category(value: object) -> Category:
    if isinstance(value, Category):
        return value
    if isinstance(value, str):
        try:
            return Category(value.strip())
        except ValueError as exc:
            raise RoutingRulesError(f"unknown category: {value.strip()}") from exc
    raise RoutingRulesError("category must be one of the shared category labels")


def _as_priority(value: object) -> Priority:
    if isinstance(value, Priority):
        return value
    if isinstance(value, str):
        try:
            return Priority(value.strip())
        except ValueError as exc:
            raise RoutingRulesError("priority must be P1, P2, P3, or P4") from exc
    raise RoutingRulesError("priority must be P1, P2, P3, or P4")
