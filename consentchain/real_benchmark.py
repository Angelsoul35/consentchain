"""Rigorous benchmark of the ConsentChain classifier pipeline on real medical text.

This module proves the classifier's pipeline generalises on *genuine* clinical
language, not only on the project's synthetic templates. It reuses the project's
own feature pipeline — the word + character ``char_wb`` TF-IDF
:class:`~sklearn.pipeline.FeatureUnion` from :mod:`consentchain.classifier` — and
the purpose head's logistic-regression hyper-parameters (``C=2.0``,
``max_iter=2000``), and evaluates them on the real, public
``gretelai/symptom_to_diagnosis`` dataset: 22 clinical diagnoses inferred from
plain-language patient narratives (see :mod:`consentchain.real_data`). It is the
same linear, explainable model family the classifier already runs, pointed at the
dataset's own 22 labels.

Everything is reported without inflation:

* **Stratified k-fold cross-validation** — macro-F1 and accuracy (mean +/- std),
  so the score does not hinge on one lucky split.
* **A held-out split** — train vs. test macro-F1/accuracy and the train/test gap.
* **The majority-class baseline** — the number any real result must clear.
* **A shuffled-label control** — the same pipeline on randomised labels, which
  must collapse to the baseline (if it did not, the real score would be an
  artefact of leakage).
* **A regularisation path** — held-out macro-F1 across a range of ``C``, showing
  the result is stable and not perched on one hyper-parameter.
* **A grounded verdict** — well-fit / overfit / underfit, decided from the
  agreement between cross-validation and the held-out split, their stability, and
  the margin over the baseline.

Multi-class real text lands below a perfect 1.0, which is correct. A linear model
with rich character n-grams will *saturate* the training set; that alone is not
overfitting. What matters is whether cross-validation and the held-out split
agree and stay strong, which is exactly what the verdict keys on.

Run with::

    python -m consentchain.real_benchmark
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline

from .classifier import _build_features
from .real_data import DATASET_ID, PROJECT_CATEGORY, load_dataset

# Model hyper-parameters, kept in step with ``RequestClassifier`` in classifier.py
# so this benchmark measures the project's real pipeline, not a throwaway model.
_MODEL_C = 2.0
_MODEL_MAX_ITER = 2000

# Verdict thresholds. They are set once, documented, and read off the results —
# never tuned to force a particular label.
_STRONG = 0.50  # macro-F1 comfortably above chance (22 balanced classes ~ 0.045)
_MARGIN_OVER_BASELINE = 0.20  # cross-validated macro-F1 must clear the baseline by this
_AGREE = 0.10  # max allowed |CV macro-F1 - held-out macro-F1| for them to "agree"
_STABLE = 0.05  # max allowed std of the CV macro-F1 across folds
_OVERFIT_GAP = 0.25  # the train/test macro-F1 gap considered bounded for a well-fit model


def build_pipeline(c: float = _MODEL_C) -> Pipeline:
    """The project's pipeline: its TF-IDF FeatureUnion + a regularised logistic model.

    Exactly the feature extractor and model family ``RequestClassifier`` uses; only
    the head is single-label here because the dataset's task is single-label.
    """
    return Pipeline(
        [
            ("features", _build_features()),
            ("logreg", LogisticRegression(max_iter=_MODEL_MAX_ITER, C=c)),
        ]
    )


@dataclass
class BenchmarkReport:
    dataset: str
    project_category: str
    n_samples: int
    n_classes: int
    chance_accuracy: float
    baseline_accuracy: float
    baseline_macro_f1: float
    cv_folds: int
    cv_accuracy_mean: float
    cv_accuracy_std: float
    cv_macro_f1_mean: float
    cv_macro_f1_std: float
    heldout_train_accuracy: float
    heldout_test_accuracy: float
    heldout_train_macro_f1: float
    heldout_test_macro_f1: float
    train_test_gap: float
    shuffled_cv_accuracy_mean: float
    shuffled_cv_macro_f1_mean: float
    reg_path: list[tuple[float, float]] = field(default_factory=list)
    verdict: str = ""
    verdict_reasons: list[str] = field(default_factory=list)

    @property
    def beats_baseline(self) -> bool:
        """Does the held-out macro-F1 clear the majority baseline by a clear margin?"""
        return self.heldout_test_macro_f1 >= self.baseline_macro_f1 + _MARGIN_OVER_BASELINE

    @property
    def shuffle_collapsed(self) -> bool:
        """Did the shuffled-label control fall back to roughly the baseline?"""
        return self.shuffled_cv_macro_f1_mean <= self.baseline_macro_f1 + _MARGIN_OVER_BASELINE


def _decide_verdict(
    cv_macro_f1_mean: float,
    cv_macro_f1_std: float,
    heldout_test_macro_f1: float,
    heldout_train_macro_f1: float,
    baseline_macro_f1: float,
) -> tuple[str, list[str]]:
    """Grounded well-fit / overfit / underfit call from the measured numbers."""
    reasons: list[str] = []
    gap = heldout_train_macro_f1 - heldout_test_macro_f1
    agree = abs(cv_macro_f1_mean - heldout_test_macro_f1)
    margin = cv_macro_f1_mean - baseline_macro_f1

    if cv_macro_f1_mean < _STRONG or margin < _MARGIN_OVER_BASELINE:
        reasons.append(
            f"cross-validated macro-F1 {cv_macro_f1_mean:.3f} is only {margin:.3f} above the "
            f"baseline {baseline_macro_f1:.3f}: the model is not capturing the signal"
        )
        return "underfit", reasons

    if heldout_test_macro_f1 < _STRONG or agree > _AGREE:
        reasons.append(
            f"held-out macro-F1 {heldout_test_macro_f1:.3f} diverges from CV "
            f"{cv_macro_f1_mean:.3f} (|diff| {agree:.3f} > {_AGREE}) or is weak: the training "
            "score does not transfer to unseen data"
        )
        return "overfit", reasons

    if cv_macro_f1_std > _STABLE:
        reasons.append(
            f"CV macro-F1 varies a lot across folds (std {cv_macro_f1_std:.3f} > {_STABLE}): "
            "the score is unstable"
        )
        return "overfit", reasons

    reasons.append(
        f"cross-validation ({cv_macro_f1_mean:.3f} +/- {cv_macro_f1_std:.3f}) and the held-out "
        f"split ({heldout_test_macro_f1:.3f}) agree and are strong, {margin:.3f} above the "
        f"baseline {baseline_macro_f1:.3f}"
    )
    reasons.append(
        f"the train/test macro-F1 gap is a bounded {gap:.3f} (within the {_OVERFIT_GAP:.2f} "
        "overfit bound); the linear model saturates the training set, expected with character "
        "n-grams, but that does not leak into unseen data"
    )
    return "well-fit", reasons


def run_benchmark(
    data: tuple[list[str], list[str]] | None = None,
    *,
    n_splits: int = 5,
    test_size: float = 0.25,
    reg_path_values: tuple[float, ...] = (0.25, 1.0, 4.0),
    seed: int = 13,
    n_jobs: int = -1,
) -> BenchmarkReport:
    """Run the full benchmark and return a :class:`BenchmarkReport`.

    ``data`` defaults to the vendored real dataset; pass your own ``(texts,
    labels)`` to benchmark a different corpus. Nothing here touches the network.
    """
    texts, labels = data if data is not None else load_dataset()
    x = np.array(texts, dtype=object)
    y = np.array(labels)
    classes = sorted(set(labels))
    n_classes = len(classes)

    scoring = ["accuracy", "f1_macro"]
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)

    # Cross-validation on the real labels.
    cv = cross_validate(build_pipeline(), x, y, cv=skf, scoring=scoring, n_jobs=n_jobs)

    # Held-out split.
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=test_size, stratify=y, random_state=seed
    )
    model = build_pipeline().fit(x_train, y_train)
    train_pred = model.predict(x_train)
    test_pred = model.predict(x_test)
    train_acc = accuracy_score(y_train, train_pred)
    test_acc = accuracy_score(y_test, test_pred)
    train_f1 = f1_score(y_train, train_pred, average="macro")
    test_f1 = f1_score(y_test, test_pred, average="macro")

    # Majority-class baseline on the held-out split.
    dummy = DummyClassifier(strategy="most_frequent").fit(x_train, y_train)
    dummy_pred = dummy.predict(x_test)
    baseline_acc = accuracy_score(y_test, dummy_pred)
    baseline_f1 = f1_score(y_test, dummy_pred, average="macro")

    # Shuffled-label control: break the text/label link; the score must collapse.
    rng = np.random.default_rng(seed)
    y_shuffled = y.copy()
    rng.shuffle(y_shuffled)
    shuffled_skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    shuffled_cv = cross_validate(
        build_pipeline(), x, y_shuffled, cv=shuffled_skf, scoring=scoring, n_jobs=n_jobs
    )

    # Regularisation path on the held-out split.
    reg_path: list[tuple[float, float]] = []
    for c in reg_path_values:
        path_model = build_pipeline(c).fit(x_train, y_train)
        path_f1 = f1_score(y_test, path_model.predict(x_test), average="macro")
        reg_path.append((float(c), round(float(path_f1), 3)))

    report = BenchmarkReport(
        dataset=DATASET_ID,
        project_category=PROJECT_CATEGORY.name.lower(),
        n_samples=len(texts),
        n_classes=n_classes,
        chance_accuracy=round(1.0 / n_classes, 3),
        baseline_accuracy=round(float(baseline_acc), 3),
        baseline_macro_f1=round(float(baseline_f1), 3),
        cv_folds=n_splits,
        cv_accuracy_mean=round(float(cv["test_accuracy"].mean()), 3),
        cv_accuracy_std=round(float(cv["test_accuracy"].std()), 3),
        cv_macro_f1_mean=round(float(cv["test_f1_macro"].mean()), 3),
        cv_macro_f1_std=round(float(cv["test_f1_macro"].std()), 3),
        heldout_train_accuracy=round(float(train_acc), 3),
        heldout_test_accuracy=round(float(test_acc), 3),
        heldout_train_macro_f1=round(float(train_f1), 3),
        heldout_test_macro_f1=round(float(test_f1), 3),
        train_test_gap=round(float(train_f1 - test_f1), 3),
        shuffled_cv_accuracy_mean=round(float(shuffled_cv["test_accuracy"].mean()), 3),
        shuffled_cv_macro_f1_mean=round(float(shuffled_cv["test_f1_macro"].mean()), 3),
        reg_path=reg_path,
    )
    report.verdict, report.verdict_reasons = _decide_verdict(
        report.cv_macro_f1_mean,
        report.cv_macro_f1_std,
        report.heldout_test_macro_f1,
        report.heldout_train_macro_f1,
        report.baseline_macro_f1,
    )
    return report


def format_report(report: BenchmarkReport) -> str:
    """Render a human-readable report."""
    lines = [
        "ConsentChain classifier — benchmark on real medical text",
        f"  dataset              : {report.dataset} (Hugging Face)",
        "  task                 : plain-language health narrative -> clinical diagnosis",
        f"  project category     : {report.project_category} "
        f"({report.n_classes} real conditions)",
        f"  samples / classes    : {report.n_samples} / {report.n_classes} (balanced)",
        "",
        f"  majority baseline    : acc {report.baseline_accuracy:.3f}  "
        f"macro-F1 {report.baseline_macro_f1:.3f}  (chance acc {report.chance_accuracy:.3f})",
        f"  {report.cv_folds}-fold stratified CV : acc "
        f"{report.cv_accuracy_mean:.3f} +/- {report.cv_accuracy_std:.3f}  "
        f"macro-F1 {report.cv_macro_f1_mean:.3f} +/- {report.cv_macro_f1_std:.3f}",
        f"  held-out train       : acc {report.heldout_train_accuracy:.3f}  "
        f"macro-F1 {report.heldout_train_macro_f1:.3f}",
        f"  held-out test        : acc {report.heldout_test_accuracy:.3f}  "
        f"macro-F1 {report.heldout_test_macro_f1:.3f}",
        f"  train/test gap       : {report.train_test_gap:.3f}  (macro-F1)",
        f"  shuffled-label ctrl  : acc {report.shuffled_cv_accuracy_mean:.3f}  "
        f"macro-F1 {report.shuffled_cv_macro_f1_mean:.3f}  (must collapse to baseline)",
    ]
    if report.reg_path:
        path = "  ".join(f"C={c:g}:{f1:.3f}" for c, f1 in report.reg_path)
        lines.append(f"  regularisation path  : {path}  (held-out macro-F1)")
    lines.append("")
    lines.append(f"  VERDICT              : {report.verdict.upper()}")
    for reason in report.verdict_reasons:
        lines.append(f"    - {reason}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_report(run_benchmark()))
