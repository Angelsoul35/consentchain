"""Tests for the real-dataset loader and the classifier benchmark.

These are functional and mutation-proven: each asserts on the *real* vendored
data and the project's real pipeline, so breaking the loader, the pipeline reuse,
the baseline, the shuffle control, or the verdict logic makes a test fail.
"""

from __future__ import annotations

import json
import urllib.error
from collections import Counter

import numpy as np
import pytest

from consentchain import real_data
from consentchain.real_benchmark import (
    _decide_verdict,
    build_pipeline,
    format_report,
    run_benchmark,
)
from consentchain.real_data import (
    DATASET_ID,
    PER_CLASS,
    PROJECT_CATEGORY,
    DatasetFetchError,
    fetch_balanced_dataset,
    fetch_rows,
    fetch_split,
    load_dataset,
    write_jsonl,
)
from consentchain.scopes import DataCategory

N_CLASSES = 22
N_ROWS = PER_CLASS * N_CLASSES


# --------------------------------------------------------------------------- #
# The vendored real dataset: counts, classes, balance, mapping.
# --------------------------------------------------------------------------- #


def test_vendored_dataset_is_real_balanced_and_classed():
    texts, labels = load_dataset()
    assert len(texts) == len(labels) == N_ROWS
    counts = Counter(labels)
    # Exactly 22 classes, each with PER_CLASS rows (perfectly balanced).
    assert len(counts) == N_CLASSES
    assert set(counts.values()) == {PER_CLASS}
    # Real labels from gretelai/symptom_to_diagnosis, not the project's templates.
    assert {"impetigo", "malaria", "diabetes", "migraine", "psoriasis"} <= set(labels)
    # Real first-person patient narratives, not generated access-request templates.
    assert all(isinstance(t, str) and t.strip() for t in texts)
    assert sum(t.lower().startswith("i ") or " my " in t.lower() for t in texts) > N_ROWS // 2


def test_label_mapping_to_project_category():
    # Every diagnosis label is an instance of the ConsentChain DIAGNOSES category.
    assert PROJECT_CATEGORY is DataCategory.DIAGNOSES
    assert PROJECT_CATEGORY.name.lower() == "diagnoses"


def test_load_dataset_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_dataset(tmp_path / "does-not-exist.jsonl")


def test_write_and_load_roundtrip(tmp_path):
    rows = [("the patient reports a fever", "malaria"), ("itchy red rash", "psoriasis")]
    path = write_jsonl(rows, tmp_path / "subset.jsonl")
    assert path.exists()
    texts, labels = load_dataset(path)
    assert texts == ["the patient reports a fever", "itchy red rash"]
    assert labels == ["malaria", "psoriasis"]


def test_load_dataset_skips_blank_lines(tmp_path):
    path = tmp_path / "with_blanks.jsonl"
    path.write_text(
        json.dumps({"text": "a", "label": "x"}) + "\n\n" + json.dumps({"text": "b", "label": "y"}),
        encoding="utf-8",
    )
    texts, labels = load_dataset(path)
    assert texts == ["a", "b"] and labels == ["x", "y"]


# --------------------------------------------------------------------------- #
# The fetch path, fully monkeypatched (no network).
# --------------------------------------------------------------------------- #


def _payload(rows, total):
    return {
        "rows": [{"row": {"input_text": t, "output_text": label}} for t, label in rows],
        "num_rows_total": total,
    }


def test_fetch_rows_parses_strips_and_filters(monkeypatch):
    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        return _payload([("  I feel sick  ", "Flu"), ("", "dropme"), ("ok", "")], 1)

    monkeypatch.setattr(real_data, "_http_get_json", fake_get)
    pairs, total = fetch_rows(0, 100, split="train")
    assert total == 1
    # whitespace stripped, label lowercased, rows with empty text/label dropped.
    assert pairs == [("I feel sick", "flu")]
    assert DATASET_ID.replace("/", "%2F") in captured["url"]
    assert "split=train" in captured["url"] and "offset=0" in captured["url"]


def test_fetch_split_paginates(monkeypatch):
    import urllib.parse as up

    pages = {0: _payload([("a", "x")] * 100, 150), 100: _payload([("b", "y")] * 50, 150)}

    def fake_get(url, **kwargs):
        offset = int(up.parse_qs(up.urlparse(url).query)["offset"][0])
        return pages[offset]

    monkeypatch.setattr(real_data, "_http_get_json", fake_get)
    pairs = fetch_split("train")
    assert len(pairs) == 150
    assert Counter(label for _, label in pairs) == {"x": 100, "y": 50}


def test_fetch_balanced_dataset_balances_and_is_deterministic(monkeypatch):
    def fake_split(split, *, dataset=DATASET_ID):
        return [(f"alpha text {i} {split}", "alpha") for i in range(5)] + [
            (f"beta text {i} {split}", "beta") for i in range(5)
        ]

    monkeypatch.setattr(real_data, "fetch_split", fake_split)
    rows = fetch_balanced_dataset(per_class=3, splits=("train", "test"))
    assert Counter(label for _, label in rows) == {"alpha": 3, "beta": 3}
    # Deterministic, sorted by (label, text) regardless of fetch order.
    assert rows == sorted(rows, key=lambda pair: (pair[1], pair[0]))
    assert rows == fetch_balanced_dataset(per_class=3, splits=("test", "train"))


def test_fetch_balanced_dataset_raises_when_class_too_small(monkeypatch):
    monkeypatch.setattr(
        real_data, "fetch_split", lambda split, *, dataset=DATASET_ID: [("only one", "alpha")]
    )
    with pytest.raises(DatasetFetchError):
        fetch_balanced_dataset(per_class=3, splits=("train",))


def test_http_get_json_rejects_non_https():
    with pytest.raises(ValueError):
        real_data._http_get_json("http://insecure.example/rows")


def test_http_get_json_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps({"rows": [], "num_rows_total": 0}).encode("utf-8")

    def fake_urlopen(request, timeout=None):
        calls["n"] += 1
        if calls["n"] < 2:
            raise urllib.error.URLError("transient")
        return FakeResponse()

    monkeypatch.setattr(real_data.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(real_data.time, "sleep", lambda _s: None)
    out = real_data._http_get_json("https://ok.example/rows", retries=3)
    assert out == {"rows": [], "num_rows_total": 0}
    assert calls["n"] == 2  # failed once, then succeeded


def test_http_get_json_raises_after_exhausting_retries(monkeypatch):
    def fake_urlopen(request, timeout=None):
        raise urllib.error.URLError("down")

    monkeypatch.setattr(real_data.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(real_data.time, "sleep", lambda _s: None)
    with pytest.raises(DatasetFetchError):
        real_data._http_get_json("https://ok.example/rows", retries=2)


def test_regenerate_writes_vendored_file(monkeypatch, tmp_path):
    monkeypatch.setattr(
        real_data,
        "fetch_balanced_dataset",
        lambda: [("text a", "alpha"), ("text b", "beta")],
    )
    out = real_data.regenerate(tmp_path / "out.jsonl")
    assert out.exists()
    _texts, labels = load_dataset(out)
    assert labels == ["alpha", "beta"]


# --------------------------------------------------------------------------- #
# The benchmark on the real pipeline. Computed once, asserted many ways.
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def report():
    return run_benchmark()


def test_pipeline_reuses_the_project_feature_union_and_hyperparameters():
    pipe = build_pipeline()
    logreg = pipe.named_steps["logreg"]
    assert logreg.C == 2.0 and logreg.max_iter == 2000
    # The same word + char TF-IDF FeatureUnion the classifier builds.
    assert [name for name, _ in pipe.named_steps["features"].transformer_list] == ["word", "char"]


def test_benchmark_beats_the_baseline_on_heldout(report):
    assert report.baseline_macro_f1 < 0.10  # majority baseline is near zero macro-F1
    assert report.heldout_test_macro_f1 >= report.baseline_macro_f1 + 0.20
    assert report.heldout_test_accuracy > report.baseline_accuracy
    assert report.beats_baseline


def test_benchmark_verdict_is_well_fit(report):
    assert report.verdict == "well-fit"
    # Strong but below a perfect 1.0 — correct for 22-way real text.
    assert 0.5 < report.heldout_test_macro_f1 < 1.0
    # Stable across folds and CV agrees with the held-out split.
    assert report.cv_macro_f1_std <= 0.05
    assert abs(report.cv_macro_f1_mean - report.heldout_test_macro_f1) <= 0.10
    # Bounded overfitting gap even though the linear model saturates train.
    assert report.heldout_train_macro_f1 >= 0.95
    assert report.train_test_gap < 0.25


def test_shuffled_label_control_collapses(report):
    assert report.shuffle_collapsed
    # Randomised labels destroy the signal: back down to roughly chance.
    assert report.shuffled_cv_macro_f1_mean < 0.15
    assert report.shuffled_cv_accuracy_mean < report.chance_accuracy + 0.10


def test_report_metadata_and_rendering(report):
    assert report.dataset == DATASET_ID
    assert report.project_category == "diagnoses"
    assert report.n_samples == N_ROWS and report.n_classes == N_CLASSES
    assert len(report.reg_path) == 3
    # Regularisation path stays strong across two orders of magnitude of C.
    assert all(f1 > 0.80 for _c, f1 in report.reg_path)
    rendered = format_report(report)
    assert "WELL-FIT" in rendered
    assert "majority baseline" in rendered
    assert "shuffled-label" in rendered


def test_verdict_rejects_label_shuffled_data():
    # Mutation proof: the same pipeline on label-shuffled real text must NOT be
    # judged well-fit. This is what distinguishes a real result from noise.
    texts, labels = load_dataset()
    rng = np.random.default_rng(0)
    shuffled = list(labels)
    rng.shuffle(shuffled)
    noise = run_benchmark((texts, shuffled), n_splits=3, reg_path_values=())
    assert noise.verdict == "underfit"
    assert not noise.beats_baseline
    assert noise.reg_path == []


def test_decide_verdict_covers_each_branch():
    # (cv_mean, cv_std, heldout_test, heldout_train, baseline)
    assert _decide_verdict(0.10, 0.01, 0.10, 0.12, 0.05)[0] == "underfit"
    assert _decide_verdict(0.90, 0.01, 0.40, 0.99, 0.05)[0] == "overfit"  # weak held-out
    assert _decide_verdict(0.90, 0.01, 0.70, 0.99, 0.05)[0] == "overfit"  # CV/held-out disagree
    assert _decide_verdict(0.80, 0.10, 0.78, 0.99, 0.05)[0] == "overfit"  # unstable folds
    assert _decide_verdict(0.90, 0.01, 0.88, 0.99, 0.05)[0] == "well-fit"
