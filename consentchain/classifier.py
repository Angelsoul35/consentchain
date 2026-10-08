"""Classify a free-text access request into a purpose and data categories.

The model is deliberately simple and explainable: a TF-IDF vectoriser feeds a
logistic-regression classifier for the purpose (one of four) and a one-vs-rest
logistic regression for the categories (a multi-label problem). Both are linear,
so for any prediction we can read off which words pushed the decision, which is
exactly what a consent system needs to be auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier

from .generate import ALL_CATEGORIES, make_dataset
from .scopes import Purpose, categories_to_mask


@dataclass
class ClassifiedRequest:
    purpose: Purpose
    purpose_confidence: float
    category_mask: int
    category_names: list[str]
    top_terms: list[tuple[str, float]] = field(default_factory=list)


class RequestClassifier:
    def __init__(self, category_threshold: float = 0.5) -> None:
        self.category_threshold = category_threshold
        self._vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=2)
        self._purpose = LogisticRegression(max_iter=1000, C=4.0)
        self._category = OneVsRestClassifier(LogisticRegression(max_iter=1000, C=4.0))
        self._fitted = False

    def fit(
        self,
        texts: list[str] | None = None,
        y_purpose: list[int] | None = None,
        y_cat: np.ndarray | None = None,
    ) -> RequestClassifier:
        if texts is None:
            texts, y_purpose, y_cat = make_dataset()
        x = self._vectorizer.fit_transform(texts)
        self._purpose.fit(x, y_purpose)
        self._category.fit(x, y_cat)
        self._fitted = True
        return self

    def _explain(self, x_row, predicted_class_index: int, k: int = 4) -> list[tuple[str, float]]:
        coef = self._purpose.coef_[predicted_class_index]
        contributions = x_row.toarray().ravel() * coef
        terms = self._vectorizer.get_feature_names_out()
        order = np.argsort(contributions)[::-1]
        top = [(terms[i], round(float(contributions[i]), 4)) for i in order if contributions[i] > 0]
        return top[:k]

    def classify(self, text: str) -> ClassifiedRequest:
        if not self._fitted:
            raise RuntimeError("Classifier is not fitted. Call fit() first.")
        x = self._vectorizer.transform([text])

        proba = self._purpose.predict_proba(x)[0]
        class_index = int(np.argmax(proba))
        purpose = Purpose(int(self._purpose.classes_[class_index]))
        confidence = float(proba[class_index])

        cat_scores = self._category.predict_proba(x)[0]
        chosen = [
            ALL_CATEGORIES[i]
            for i, score in enumerate(cat_scores)
            if score >= self.category_threshold
        ]
        # A request should ask for something; if nothing clears the threshold,
        # fall back to the single most likely category so the policy can still
        # reason about it.
        if not chosen:
            chosen = [ALL_CATEGORIES[int(np.argmax(cat_scores))]]

        return ClassifiedRequest(
            purpose=purpose,
            purpose_confidence=round(confidence, 4),
            category_mask=categories_to_mask(chosen),
            category_names=[c.name.lower() for c in chosen],
            top_terms=self._explain(x, class_index),
        )
