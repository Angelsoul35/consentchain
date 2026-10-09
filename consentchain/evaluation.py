"""Rigorous, leakage-free evaluation of the request classifier.

Within-distribution accuracy on templated data is misleadingly high, so this
module trains on one pool of phrasings and tests on a *disjoint* pool: the test
sentences use wording the model never saw. It reports purpose accuracy, category
micro-F1, and the train/test gap (large gap = overfitting, low scores = underfit).

Run with ``python -m consentchain.evaluation``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.metrics import accuracy_score, f1_score

from .classifier import RequestClassifier
from .generate import make_split_datasets


@dataclass
class EvalReport:
    purpose_accuracy: float
    purpose_train_accuracy: float
    purpose_gap: float
    category_micro_f1: float
    n_train: int
    n_test: int


def phrase_disjoint_eval(seed: int = 13, holdout_frac: float = 0.3) -> EvalReport:
    tr_texts, tr_yp, tr_yc, te_texts, te_yp, te_yc = make_split_datasets(
        seed=seed, holdout_frac=holdout_frac
    )
    clf = RequestClassifier().fit(tr_texts, tr_yp, tr_yc)

    te_pred_p = [int(clf.classify(t).purpose) for t in te_texts]
    tr_pred_p = [int(clf.classify(t).purpose) for t in tr_texts]

    # Category micro-F1 on the held-out phrasings.
    from .scopes import mask_to_categories

    def cat_matrix(texts):
        rows = []
        for t in texts:
            mask = clf.classify(t).category_mask
            present = {c for c in mask_to_categories(mask)}
            from .generate import ALL_CATEGORIES

            rows.append([1 if c in present else 0 for c in ALL_CATEGORIES])
        return np.array(rows)

    pred_cat = cat_matrix(te_texts)

    test_acc = accuracy_score(te_yp, te_pred_p)
    train_acc = accuracy_score(tr_yp, tr_pred_p)
    return EvalReport(
        purpose_accuracy=round(float(test_acc), 3),
        purpose_train_accuracy=round(float(train_acc), 3),
        purpose_gap=round(float(train_acc - test_acc), 3),
        category_micro_f1=round(
            float(f1_score(np.array(te_yc), pred_cat, average="micro", zero_division=0)), 3
        ),
        n_train=len(tr_texts),
        n_test=len(te_texts),
    )


if __name__ == "__main__":
    r = phrase_disjoint_eval()
    print("Phrase-disjoint evaluation (test wording never seen in training):")
    print(f"  train / test size    : {r.n_train} / {r.n_test}")
    print(f"  purpose accuracy     : {r.purpose_accuracy}")
    print(f"  purpose train acc    : {r.purpose_train_accuracy}")
    print(f"  purpose train-test gap: {r.purpose_gap}  (small = not overfit)")
    print(f"  category micro-F1    : {r.category_micro_f1}")
