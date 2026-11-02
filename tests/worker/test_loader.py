# The export files load without starting the training notebook.
# Cleaning and encoding follow text_prep.json and word2idx.json.
# A missing or mismatched file is rejected before a score is returned.

import hashlib
import json
from pathlib import Path

import pytest

from desktriage_common.enums import Category, Priority
from worker.app.classifier.loader import (
    ClassifierLoadError,
    TextPrep,
    Vocabulary,
    _check_head_widths,
    _file_identity,
    _load_categories,
    _load_priorities,
    _load_text_prep,
    _load_vocabulary,
    clean_text,
    encode,
    load_classifier,
    models_dir,
)


def _write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _vocabulary() -> dict[str, object]:
    return {
        "word2idx": {"<PAD>": 0, "<OOV>": 1, "claim": 2},
        "max_len": 4,
        "pad_idx": 0,
        "oov_idx": 1,
    }


def _prep() -> dict[str, object]:
    return {
        "fields": ["query_text", "escalation_reason"],
        "lowercase": True,
        "contractions": {"don't": "do not"},
        "keep_tokens": ["?", "!"],
    }


class _Width:
    def __init__(self, width: int) -> None:
        self.shape = (None, width)


def test_models_dir_uses_the_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MODELS_DIR", str(tmp_path))
    assert models_dir() == tmp_path


def test_a_blank_models_dir_uses_the_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODELS_DIR", "   ")
    assert models_dir().name == "models"


def test_a_missing_model_file_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("MODELS_DIR", str(tmp_path))
    load_classifier.cache_clear()
    try:
        with pytest.raises(ClassifierLoadError, match="classifier file not found"):
            load_classifier()
    finally:
        load_classifier.cache_clear()


def test_file_identity_is_the_sha256(tmp_path: Path) -> None:
    path = tmp_path / "classifier.keras"
    path.write_bytes(b"abc")
    assert _file_identity(path) == hashlib.sha256(b"abc").hexdigest()


def test_the_shipped_export_matches_the_shared_labels() -> None:
    directory = Path(__file__).resolve().parents[2] / "models"
    prep = _load_text_prep(directory / "text_prep.json")
    vocabulary = _load_vocabulary(directory / "word2idx.json")
    categories = _load_categories(directory / "category_labels.json")
    priorities = _load_priorities(directory / "priority_labels.json")

    assert prep.lowercase is True
    assert vocabulary.max_len == 48
    assert vocabulary.pad_idx == vocabulary.word2idx["<PAD>"]
    assert vocabulary.oov_idx == vocabulary.word2idx["<OOV>"]
    assert categories == (
        Category.ELIGIBILITY_AND_ENROLLMENT,
        Category.COVERAGE_AND_BENEFITS,
        Category.CLAIMS_AND_APPEALS,
        Category.COSTS_AND_FINANCIAL_ASSISTANCE,
        Category.ACCESS_AND_REFERRALS,
        Category.POLICY_INTERPRETATION,
        Category.OTHER_OR_UNKNOWN,
    )
    assert priorities == (Priority.P1, Priority.P2, Priority.P3, Priority.P4)


def test_vocabulary_requires_a_token_map(tmp_path: Path) -> None:
    path = tmp_path / "word2idx.json"
    _write(path, [])
    with pytest.raises(ClassifierLoadError, match="mapping"):
        _load_vocabulary(path)


def test_an_empty_vocabulary_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "word2idx.json"
    payload = _vocabulary()
    payload["word2idx"] = {}
    _write(path, payload)
    with pytest.raises(ClassifierLoadError, match="word2idx"):
        _load_vocabulary(path)


def test_a_boolean_index_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "word2idx.json"
    payload = _vocabulary()
    payload["word2idx"] = {"claim": True}
    _write(path, payload)
    with pytest.raises(ClassifierLoadError, match="indexes"):
        _load_vocabulary(path)


def test_max_len_must_be_positive(tmp_path: Path) -> None:
    path = tmp_path / "word2idx.json"
    payload = _vocabulary()
    payload["max_len"] = 0
    _write(path, payload)
    with pytest.raises(ClassifierLoadError, match="max_len"):
        _load_vocabulary(path)


def test_text_prep_must_name_both_fields(tmp_path: Path) -> None:
    path = tmp_path / "text_prep.json"
    payload = _prep()
    payload["fields"] = ["query_text"]
    _write(path, payload)
    with pytest.raises(ClassifierLoadError, match="query_text and escalation_reason"):
        _load_text_prep(path)


def test_lowercase_must_be_boolean(tmp_path: Path) -> None:
    path = tmp_path / "text_prep.json"
    payload = _prep()
    payload["lowercase"] = "yes"
    _write(path, payload)
    with pytest.raises(ClassifierLoadError, match="lowercase"):
        _load_text_prep(path)


def test_an_unknown_category_label_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "category_labels.json"
    _write(path, ["not_a_category"])
    with pytest.raises(ClassifierLoadError, match="unknown category"):
        _load_categories(path)


def test_a_priority_label_is_trimmed(tmp_path: Path) -> None:
    path = tmp_path / "priority_labels.json"
    _write(path, [" P1 ", "P2", "P3", "P4"])
    assert _load_priorities(path)[0] is Priority.P1


def test_an_empty_label_list_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "priority_labels.json"
    _write(path, [])
    with pytest.raises(ClassifierLoadError, match="non-empty"):
        _load_priorities(path)


def test_head_widths_must_match_the_label_files() -> None:
    model = type("Model", (), {"output": {"category": _Width(7), "priority": _Width(4)}})()
    _check_head_widths(model, tuple(Category), tuple(Priority))


def test_a_short_category_head_is_rejected() -> None:
    model = type("Model", (), {"output": {"category": _Width(6), "priority": _Width(4)}})()
    with pytest.raises(ClassifierLoadError, match="category head"):
        _check_head_widths(model, tuple(Category), tuple(Priority))


def test_a_model_without_named_heads_is_rejected() -> None:
    model = type("Model", (), {"output": ["category", "priority"]})()
    with pytest.raises(ClassifierLoadError, match="category and priority"):
        _check_head_widths(model, tuple(Category), tuple(Priority))


def test_cleaning_expands_contractions_and_keeps_punctuation() -> None:
    prep = TextPrep(
        lowercase=True,
        contractions=(("don't", "do not"), ("it's", "it is")),
        keep_tokens=("?", "!"),
    )
    assert clean_text("Don't wait!", prep) == ["do", "not", "wait", "!"]
    assert clean_text("It\u2019s fine?", prep) == ["it", "is", "fine", "?"]
    assert clean_text("plan 2026...", prep) == ["plan", "2026"]


def test_cleaning_can_keep_the_original_case() -> None:
    prep = TextPrep(lowercase=False, contractions=(), keep_tokens=())
    assert clean_text("Claim", prep) == ["Claim"]


def test_encode_pads_unknown_tokens_and_trims_on_the_right() -> None:
    vocabulary = Vocabulary(
        word2idx={"<PAD>": 0, "<OOV>": 1, "claim": 2},
        max_len=4,
        pad_idx=0,
        oov_idx=1,
    )
    padded = encode(["claim", "missing"], vocabulary)
    assert padded.dtype.name == "int32"
    assert padded.tolist() == [[2, 1, 0, 0]]
    assert encode(["claim"] * 6, vocabulary).tolist() == [[2, 2, 2, 2]]
    assert encode([], vocabulary).tolist() == [[0, 0, 0, 0]]
