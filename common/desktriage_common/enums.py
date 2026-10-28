"""Values the API, the worker, the config files, and the training labels share.

Categories come from dataset/desktriage_dataset_card.md. Operational priority
is P1, P2, P3, or P4. Use these when you store a decision.
"""

from enum import StrEnum


class Category(StrEnum):
    """Healthcare-policy domain assigned to a ticket."""

    ELIGIBILITY_AND_ENROLLMENT = "eligibility_and_enrollment"
    COVERAGE_AND_BENEFITS = "coverage_and_benefits"
    CLAIMS_AND_APPEALS = "claims_and_appeals"
    COSTS_AND_FINANCIAL_ASSISTANCE = "costs_and_financial_assistance"
    ACCESS_AND_REFERRALS = "access_and_referrals"
    POLICY_INTERPRETATION = "policy_interpretation"
    OTHER_OR_UNKNOWN = "other_or_unknown"


class Priority(StrEnum):
    """Operational handling priority, not clinical urgency."""

    P1 = "P1"  # immediate administrative deadline or material deadline risk
    P2 = "P2"  # time-sensitive administrative need requiring prompt review
    P3 = "P3"  # routine unresolved query
    P4 = "P4"  # non-time-sensitive information request
