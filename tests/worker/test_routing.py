# Routing maps a category the gate has accepted to the team in config/routing_rules.yaml.
# A category you have marked for human review, or a ticket the gate rejected,
# does not receive an automatic team from this module.

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
