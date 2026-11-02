# Routing maps a category the gate has accepted to the team in config/routing_rules.yaml.
# A category you have marked for human review, or a ticket the gate rejected,
# does not receive an automatic team from this module.

from pathlib import Path

import pytest

from desktriage_common.enums import Category, Priority
from worker.app.routing.rules import RoutingRulesError, destination_team


@pytest.mark.parametrize(
    ("category", "team"),
    [
        (Category.ELIGIBILITY_AND_ENROLLMENT, "enrollment_support"),
        (Category.COVERAGE_AND_BENEFITS, "benefits_support"),
        (Category.CLAIMS_AND_APPEALS, "claims_support"),
        (Category.COSTS_AND_FINANCIAL_ASSISTANCE, "financial_assistance_support"),
        (Category.ACCESS_AND_REFERRALS, "access_support"),
        (Category.POLICY_INTERPRETATION, "policy_specialist"),
    ],
)
def test_routed_category_gets_its_team(category: Category, team: str) -> None:
    assert destination_team(category, Priority.P3) == team


def test_other_or_unknown_has_no_automatic_team() -> None:
    assert destination_team(Category.OTHER_OR_UNKNOWN, Priority.P1) is None


def test_priority_does_not_change_the_team() -> None:
    category = Category.CLAIMS_AND_APPEALS
    teams = {destination_team(category, priority) for priority in Priority}
    assert teams == {"claims_support"}


def test_label_strings_are_accepted() -> None:
    assert destination_team("access_and_referrals", "P2") == "access_support"


def test_unknown_category_is_rejected() -> None:
    with pytest.raises(RoutingRulesError):
        destination_team("not_a_category", Priority.P3)


def test_an_unknown_priority_is_rejected() -> None:
    with pytest.raises(RoutingRulesError):
        destination_team(Category.CLAIMS_AND_APPEALS, "P5")


def test_a_missing_rules_file_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    with pytest.raises(RoutingRulesError, match="not found"):
        destination_team(Category.ACCESS_AND_REFERRALS, Priority.P3)


def test_rules_come_from_the_config_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    lines = ["routes:"]
    for category in Category:
        if category is Category.OTHER_OR_UNKNOWN:
            continue
        lines.append(f"  {category.value}: {category.value}_desk")
    lines.append("human_review_categories:")
    lines.append("  - other_or_unknown")
    (tmp_path / "routing_rules.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))

    assert destination_team(Category.CLAIMS_AND_APPEALS, Priority.P1) == "claims_and_appeals_desk"
    assert destination_team(Category.OTHER_OR_UNKNOWN, Priority.P4) is None


def test_rules_must_cover_every_category(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "routing_rules.yaml").write_text(
        "routes:\n  claims_and_appeals: claims_support\nhuman_review_categories: []\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    with pytest.raises(RoutingRulesError, match="do not cover"):
        destination_team(Category.CLAIMS_AND_APPEALS, Priority.P3)


def test_a_category_cannot_be_routed_and_held(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "routing_rules.yaml").write_text(
        "routes:\n"
        "  claims_and_appeals: claims_support\n"
        "human_review_categories:\n"
        "  - claims_and_appeals\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    with pytest.raises(RoutingRulesError, match="both routed and held"):
        destination_team(Category.CLAIMS_AND_APPEALS, Priority.P3)
