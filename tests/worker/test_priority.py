# The priority policy returns P1, P2, P3, or P4 from config/priority_policy.yaml.
# Cover one case for each priority you define.
# This test checks the rules the worker runs. The notebook checks those rules
# against the labelled dataset.

import pytest

from desktriage_common.enums import Priority
from worker.app.priority.policy import PriorityPolicyError, assign_priority


def test_immediate_deadline_is_p1() -> None:
    query = (
        "The policy-related deadline is within the next few hours, "
        "and the applicable steps remain unclear."
    )
    assert assign_priority(query) is Priority.P1


def test_deadline_next_week_is_p2() -> None:
    query = "I need clarification before a documented deadline next week."
    assert assign_priority(query) is Priority.P2


def test_routine_query_is_p3() -> None:
    query = "There is no immediate deadline, but I need the correct policy guidance."
    assert assign_priority(query) is Priority.P3


def test_information_request_is_p4() -> None:
    query = (
        "This is a general clarification request with no stated deadline "
        "or time-sensitive consequence."
    )
    assert assign_priority(query) is Priority.P4


def test_query_with_no_deadline_cue_uses_the_default() -> None:
    query = (
        "I need help with my policy question, but I have not included the "
        "policy name or enough details to identify the applicable section."
    )
    assert assign_priority(query) is Priority.P3


def test_match_ignores_case_and_keeps_the_earlier_rule() -> None:
    query = "The DEADLINE IS TODAY, and otherwise I can wait for the normal backlog."
    assert assign_priority(query) is Priority.P1


def test_blank_query_is_rejected() -> None:
    with pytest.raises(PriorityPolicyError):
        assign_priority("   ")
