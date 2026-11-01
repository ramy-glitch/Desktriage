"""Load the two-head classifier written by the training notebook.

classifier.keras is the shared BiLSTM, with a category head and a priority head.
word2idx.json and text_prep.json repeat the notebook's vocabulary and cleaning.
category_labels.json and priority_labels.json are the softmax index order.
model_version is the SHA-256 of classifier.keras, which trace.py can store.
Loading the network needs TensorFlow, the same library the notebook used to save it.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from desktriage_common.enums import Category, Priority

_MODEL_FILENAME = "classifier.keras"
_VOCAB_FILENAME = "word2idx.json"
_PREP_FILENAME = "text_prep.json"
_CATEGORY_LABELS_FILENAME = "category_labels.json"
_PRIORITY_LABELS_FILENAME = "priority_labels.json"

# The notebook restores curly apostrophes before the rules in text_prep.json.
_CURLY_APOSTROPHES = ("\u2018", "\u2019")


class ClassifierLoadError(ValueError):
    """The exported classifier files are missing or do not match the notebook."""


@dataclass(frozen=True)
class TextPrep:
    """Cleaning rules recorded in text_prep.json."""

    lowercase: bool
    contractions: tuple[tuple[str, str], ...]
    keep_tokens: tuple[str, ...]


@dataclass(frozen=True)
class Vocabulary:
    """Training vocabulary and the padding length from word2idx.json."""

    word2idx: Mapping[str, int]
    max_len: int
    pad_idx: int
    oov_idx: int


@dataclass(frozen=True)
class LoadedClassifier:
    """Network, vocabulary, cleaning rules, label order, and file identity."""

    model: object
    vocabulary: Vocabulary
    text_prep: TextPrep
    categories: tuple[Category, ...]
    priorities: tuple[Priority, ...]
    model_version: str


def models_dir() -> Path:
    """Resolve the export directory from MODELS_DIR, or from the repository models directory."""
    configured = os.environ.get("MODELS_DIR", "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3] / "models"


def model_version() -> str:
    """Return the SHA-256 of the loaded classifier.keras file."""
    return load_classifier().model_version


@lru_cache(maxsize=1)
def load_classifier() -> LoadedClassifier:
    """Load the exported network and its companion files once per process."""
    directory = models_dir()
    model_path = directory / _MODEL_FILENAME
    model = _load_network(model_path)
    vocabulary = _load_vocabulary(directory / _VOCAB_FILENAME)
    text_prep = _load_text_prep(directory / _PREP_FILENAME)
    categories = _load_categories(directory / _CATEGORY_LABELS_FILENAME)
    priorities = _load_priorities(directory / _PRIORITY_LABELS_FILENAME)
    _check_head_widths(model, categories, priorities)
    return LoadedClassifier(
        model=model,
        vocabulary=vocabulary,
        text_prep=text_prep,
        categories=categories,
        priorities=priorities,
        model_version=_file_identity(model_path),
    )


def clean_text(text: str, prep: TextPrep) -> list[str]:
    """Repeat the notebook's clean_text using the rules in text_prep.json.

    Query text and escalation reason are joined with a space before this call.
    Curly apostrophes become straight ones, contractions expand, and the kept
    punctuation marks stay as their own tokens. Everything else is dropped.
    """
    cleaned = str(text)
    for apostrophe in _CURLY_APOSTROPHES:
        cleaned = cleaned.replace(apostrophe, "'")
    if prep.lowercase:
        cleaned = cleaned.lower()
    for source, target in prep.contractions:
        cleaned = re.sub(rf"\b{re.escape(source)}\b", target, cleaned)

    singles = "".join(re.escape(token) for token in prep.keep_tokens if len(token) == 1)
    for token in prep.keep_tokens:
        if len(token) != 1:
            cleaned = cleaned.replace(token, f" {token} ")
    if singles:
        cleaned = re.sub(f"([{singles}])", r" \1 ", cleaned)

    letters = "a-z" if prep.lowercase else "A-Za-z"
    longer = "".join(re.escape(token) for token in prep.keep_tokens if len(token) != 1)
    cleaned = re.sub(f"[^{letters}0-9{singles}{longer} ]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.split()


def encode(tokens: list[str], vocabulary: Vocabulary) -> np.ndarray:
    """Map tokens to ids and pad or trim on the right, as the notebook does."""
    sequence = [vocabulary.word2idx.get(token, vocabulary.oov_idx) for token in tokens]
    if len(sequence) >= vocabulary.max_len:
        sequence = sequence[: vocabulary.max_len]
    else:
        sequence.extend([vocabulary.pad_idx] * (vocabulary.max_len - len(sequence)))
    return np.asarray([sequence], dtype=np.int32)


def _load_network(path: Path) -> object:
    if not path.is_file():
        raise ClassifierLoadError(f"classifier file not found: {path}")
    try:
        import tensorflow as tf
    except ImportError as exc:
        raise ClassifierLoadError(
            "TensorFlow is required to load classifier.keras"
        ) from exc
    return tf.keras.models.load_model(path)


def _load_vocabulary(path: Path) -> Vocabulary:
    loaded = _read_json(path)
    if not isinstance(loaded, Mapping):
        raise ClassifierLoadError("word2idx.json must be a mapping")
    raw_vocab = loaded.get("word2idx")
    if not isinstance(raw_vocab, Mapping) or not raw_vocab:
        raise ClassifierLoadError("word2idx.json needs a word2idx mapping")
    word2idx: dict[str, int] = {}
    for token, index in raw_vocab.items():
        if not isinstance(token, str) or isinstance(index, bool) or not isinstance(index, int):
            raise ClassifierLoadError("word2idx entries must map tokens to indexes")
        word2idx[token] = index
    return Vocabulary(
        word2idx=word2idx,
        max_len=_positive_int(loaded.get("max_len"), "max_len"),
        pad_idx=_non_negative_int(loaded.get("pad_idx"), "pad_idx"),
        oov_idx=_non_negative_int(loaded.get("oov_idx"), "oov_idx"),
    )


def _load_text_prep(path: Path) -> TextPrep:
    loaded = _read_json(path)
    if not isinstance(loaded, Mapping):
        raise ClassifierLoadError("text_prep.json must be a mapping")
    fields = loaded.get("fields")
    if fields != ["query_text", "escalation_reason"]:
        raise ClassifierLoadError(
            "text_prep.json must clean query_text and escalation_reason"
        )
    lowercase = loaded.get("lowercase")
    if not isinstance(lowercase, bool):
        raise ClassifierLoadError("text_prep.json lowercase must be true or false")
    raw_contractions = loaded.get("contractions")
    if not isinstance(raw_contractions, Mapping):
        raise ClassifierLoadError("text_prep.json contractions must be a mapping")
    contractions: list[tuple[str, str]] = []
    for source, target in raw_contractions.items():
        if not isinstance(source, str) or not isinstance(target, str):
            raise ClassifierLoadError("each contraction must map text to text")
        contractions.append((source, target))
    raw_keep = loaded.get("keep_tokens")
    if not isinstance(raw_keep, list) or not all(isinstance(token, str) for token in raw_keep):
        raise ClassifierLoadError("text_prep.json keep_tokens must be a list of strings")
    return TextPrep(
        lowercase=lowercase,
        contractions=tuple(contractions),
        keep_tokens=tuple(raw_keep),
    )


def _load_categories(path: Path) -> tuple[Category, ...]:
    return tuple(_as_category(label) for label in _label_list(path, "category_labels.json"))


def _load_priorities(path: Path) -> tuple[Priority, ...]:
    return tuple(_as_priority(label) for label in _label_list(path, "priority_labels.json"))


def _label_list(path: Path, filename: str) -> list[str]:
    loaded = _read_json(path)
    if not isinstance(loaded, list) or not loaded:
        raise ClassifierLoadError(f"{filename} must be a non-empty list")
    labels: list[str] = []
    for item in loaded:
        if not isinstance(item, str) or not item.strip():
            raise ClassifierLoadError(f"{filename} has an empty label")
        labels.append(item.strip())
    return labels


def _as_category(value: str) -> Category:
    try:
        return Category(value)
    except ValueError as exc:
        raise ClassifierLoadError(f"unknown category label: {value}") from exc


def _as_priority(value: str) -> Priority:
    try:
        return Priority(value)
    except ValueError as exc:
        raise ClassifierLoadError(f"unknown priority label: {value}") from exc


def _check_head_widths(model: object, categories: tuple[Category, ...], priorities: tuple[Priority, ...]) -> None:
    output = getattr(model, "output", None)
    if not isinstance(output, Mapping) or "category" not in output or "priority" not in output:
        raise ClassifierLoadError("classifier.keras must expose category and priority heads")
    category_width = int(output["category"].shape[-1])
    priority_width = int(output["priority"].shape[-1])
    if category_width != len(categories):
        raise ClassifierLoadError("category_labels.json does not match the category head")
    if priority_width != len(priorities):
        raise ClassifierLoadError("priority_labels.json does not match the priority head")


def _read_json(path: Path) -> object:
    if not path.is_file():
        raise ClassifierLoadError(f"classifier file not found: {path}")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _file_identity(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ClassifierLoadError(f"{name} must be a positive integer")
    return value


def _non_negative_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ClassifierLoadError(f"{name} must be a non-negative integer")
    return value
