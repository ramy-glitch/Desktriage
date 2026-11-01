"""Run the exported two-head model on query text and escalation reason.

Returns the category, the category-head confidence, the priority, and the
priority-head confidence. Confidence for the routing gate is the maximum
probability of the category head. Priority confidence is the maximum
probability of the priority head. Label names come from desktriage_common.enums.
This function does not choose a team, apply the priority threshold, or decide
human review.
"""

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from desktriage_common.enums import Category, Priority
from worker.app.classifier.loader import clean_text, encode, load_classifier


class ClassifierError(ValueError):
    """The query cannot be scored by the exported classifier."""


@dataclass(frozen=True)
class Classification:
    """Both heads for one ticket, each with its maximum probability."""

    category: Category
    confidence: float
    priority: Priority
    priority_confidence: float


def predict(query_text: str, escalation_reason: str) -> Classification:
    """Score one escalated query with the loaded two-head classifier."""
    if not isinstance(query_text, str) or not query_text.strip():
        raise ClassifierError("query_text must not be empty")
    if not isinstance(escalation_reason, str) or not escalation_reason.strip():
        raise ClassifierError("escalation_reason must not be empty")

    loaded = load_classifier()
    tokens = clean_text(f"{query_text} {escalation_reason}", loaded.text_prep)
    features = encode(tokens, loaded.vocabulary)
    category_probs, priority_probs = _head_probabilities(loaded.model, features)
    category_index = int(np.argmax(category_probs))
    priority_index = int(np.argmax(priority_probs))
    return Classification(
        category=loaded.categories[category_index],
        confidence=float(category_probs[category_index]),
        priority=loaded.priorities[priority_index],
        priority_confidence=float(priority_probs[priority_index]),
    )


def _head_probabilities(model: object, features: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    predictions = model.predict(features, verbose=0)
    if isinstance(predictions, Mapping):
        category = predictions.get("category")
        priority = predictions.get("priority")
    elif isinstance(predictions, (list, tuple)) and len(predictions) == 2:
        category, priority = predictions
    else:
        raise ClassifierError("the exported model did not return category and priority heads")
    if category is None or priority is None:
        raise ClassifierError("the exported model did not return category and priority heads")

    category_rows = np.asarray(category)
    priority_rows = np.asarray(priority)
    if category_rows.ndim != 2 or priority_rows.ndim != 2 or len(category_rows) != 1:
        raise ClassifierError("the exported model returned an unexpected probability shape")
    return category_rows[0], priority_rows[0]
