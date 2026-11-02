# The classifier returns a category from the shared enumeration and a confidence score.
# Use a tiny exported fixture or a fake loader so this test does not run the notebook.
# Assert the predicted label is one of the seven category names.

from typing import cast

import numpy as np
import pytest

from desktriage_common.enums import Category, Priority
from worker.app.classifier.loader import LoadedClassifier, TextPrep, Vocabulary
from worker.app.classifier.predict import ClassifierError, predict

_CATEGORIES = (
    Category.ELIGIBILITY_AND_ENROLLMENT,
    Category.COVERAGE_AND_BENEFITS,
    Category.CLAIMS_AND_APPEALS,
    Category.COSTS_AND_FINANCIAL_ASSISTANCE,
    Category.ACCESS_AND_REFERRALS,
    Category.POLICY_INTERPRETATION,
    Category.OTHER_OR_UNKNOWN,
)
_CATEGORY_PROBS = np.asarray([[0.02, 0.03, 0.81, 0.04, 0.03, 0.04, 0.03]])
_PRIORITY_PROBS = np.asarray([[0.1, 0.7, 0.15, 0.05]])


class _Model:
    def __init__(self, predictions: object) -> None:
        self._predictions = predictions

    def predict(self, features: np.ndarray, verbose: int = 0) -> object:
        return self._predictions


def _loaded(predictions: object) -> LoadedClassifier:
    return LoadedClassifier(
        model=_Model(predictions),
        vocabulary=Vocabulary(
            word2idx={"<PAD>": 0, "<OOV>": 1, "claim": 2},
            max_len=4,
            pad_idx=0,
            oov_idx=1,
        ),
        text_prep=TextPrep(lowercase=True, contractions=(), keep_tokens=("?",)),
        categories=_CATEGORIES,
        priorities=(Priority.P1, Priority.P2, Priority.P3, Priority.P4),
        model_version="abc123",
    )


def _install(monkeypatch: pytest.MonkeyPatch, predictions: object) -> None:
    monkeypatch.setattr(
        "worker.app.classifier.predict.load_classifier",
        lambda: _loaded(predictions),
    )


def test_predict_returns_one_of_the_seven_categories(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, {"category": _CATEGORY_PROBS, "priority": _PRIORITY_PROBS})

    scored = predict("where is my claim", "conflicting_evidence")

    assert len(Category) == 7
    assert scored.category in set(Category)
    assert scored.category is Category.CLAIMS_AND_APPEALS
    assert scored.confidence == pytest.approx(0.81)
    assert scored.priority is Priority.P2
    assert scored.priority_confidence == pytest.approx(0.7)
    assert 0.0 <= scored.confidence <= 1.0
    assert 0.0 <= scored.priority_confidence <= 1.0


def test_a_tuple_of_heads_is_scored(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, (_CATEGORY_PROBS, _PRIORITY_PROBS))

    scored = predict("where is my claim", "conflicting_evidence")

    assert scored.category is Category.CLAIMS_AND_APPEALS
    assert scored.priority is Priority.P2


def test_query_and_reason_are_scored_together(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, {"category": _CATEGORY_PROBS, "priority": _PRIORITY_PROBS})
    seen: dict[str, str] = {}

    def clean(text: str, prep: TextPrep) -> list[str]:
        seen["text"] = text
        return ["claim"]

    monkeypatch.setattr("worker.app.classifier.predict.clean_text", clean)

    predict("Appeal deadline", "human_requested")

    assert seen["text"] == "Appeal deadline human_requested"


def test_a_missing_head_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, {"category": _CATEGORY_PROBS})

    with pytest.raises(ClassifierError, match="category and priority"):
        predict("where is my claim", "conflicting_evidence")


def test_a_flat_probability_vector_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(
        monkeypatch,
        {"category": np.zeros(7), "priority": _PRIORITY_PROBS},
    )

    with pytest.raises(ClassifierError, match="shape"):
        predict("where is my claim", "conflicting_evidence")


@pytest.mark.parametrize(
    ("query_text", "escalation_reason", "match"),
    [
        ("  ", "conflicting_evidence", "query_text"),
        ("where is my claim", "  ", "escalation_reason"),
        (None, "conflicting_evidence", "query_text"),
        ("where is my claim", None, "escalation_reason"),
    ],
)
def test_blank_text_is_rejected(
    query_text: object,
    escalation_reason: object,
    match: str,
) -> None:
    with pytest.raises(ClassifierError, match=match):
        predict(cast(str, query_text), cast(str, escalation_reason))
