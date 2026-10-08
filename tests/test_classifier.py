from __future__ import annotations

import numpy as np
import pytest
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split

from consentchain.classifier import RequestClassifier
from consentchain.generate import make_dataset
from consentchain.scopes import Purpose


def test_classify_treatment_request(classifier):
    text = (
        "The treating physician needs the recent lab results and the current "
        "medication list to adjust the patient's therapy."
    )
    result = classifier.classify(text)
    assert result.purpose is Purpose.TREATMENT
    assert result.purpose_confidence > 0.5
    assert "lab_results" in result.category_names
    assert "medications" in result.category_names
    assert result.top_terms  # explanation is populated


def test_classify_research_request(classifier):
    text = "For an approved research study we request the patient's genetic test results."
    result = classifier.classify(text)
    assert result.purpose is Purpose.RESEARCH
    assert "genetic" in result.category_names


def test_unfitted_classifier_raises():
    with pytest.raises(RuntimeError):
        RequestClassifier().classify("anything")


def test_held_out_accuracy_is_high():
    texts, yp, yc = make_dataset(n=1200, seed=5)
    x_tr, x_te, yp_tr, yp_te, yc_tr, yc_te = train_test_split(
        texts, yp, yc, test_size=0.25, random_state=0
    )
    clf = RequestClassifier().fit(x_tr, yp_tr, yc_tr)

    pred_purpose = [int(clf.classify(t).purpose) for t in x_te]
    assert accuracy_score(yp_te, pred_purpose) > 0.95

    x_vec = clf._vectorizer.transform(x_te)
    proba = clf._category.predict_proba(x_vec)
    pred_cat = (proba >= 0.5).astype(int)
    assert f1_score(yc_te, pred_cat, average="micro", zero_division=0) > 0.9


def test_category_fallback_picks_most_likely():
    # A request with a weak category signal still returns at least one category.
    clf = RequestClassifier().fit()
    result = clf.classify("the care team requires information")
    assert len(result.category_names) >= 1
    assert isinstance(result.category_mask, int) and result.category_mask > 0
    # The matrix column count matches the number of categories.
    assert np.log2(result.category_mask) < 8
