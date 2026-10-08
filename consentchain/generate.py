"""Synthetic, labelled health-data access requests for training the classifier.

Each request is a short free-text sentence that a clinician, biller, auditor, or
researcher might write, labelled with the purpose it serves and the data
categories it asks for. The text is built from templates and category/purpose
phrases, so it is realistic enough to learn from and fully deterministic.
Everything here is synthetic — no real request or patient is involved.
"""

from __future__ import annotations

import numpy as np

from .scopes import DataCategory, Purpose

PURPOSE_PHRASES: dict[Purpose, list[str]] = {
    Purpose.TREATMENT: [
        "the treating physician needs",
        "the care team requires",
        "to adjust the patient's therapy we need",
        "for ongoing clinical care, please share",
        "the attending doctor is reviewing",
        "to make a treatment decision we request",
    ],
    Purpose.PAYMENT: [
        "the billing department needs",
        "to process the insurance claim we require",
        "for reimbursement, please provide",
        "to verify coverage we request",
        "the payer is auditing the claim and needs",
        "to settle the outstanding invoice we need",
    ],
    Purpose.OPERATIONS: [
        "for a quality-of-care audit we need",
        "the compliance review requires",
        "for internal care-coordination we request",
        "to improve our service we are reviewing",
        "the operations team needs",
        "for an accreditation review, please share",
    ],
    Purpose.RESEARCH: [
        "for an approved research study we request",
        "the clinical trial protocol requires",
        "for an epidemiological analysis we need",
        "the research cohort needs",
        "under the study's ethics approval we request",
        "for a registered research project, please provide",
    ],
}

CATEGORY_PHRASES: dict[DataCategory, list[str]] = {
    DataCategory.DEMOGRAPHICS: [
        "the patient's demographic details",
        "the contact information and age",
        "the basic demographic record",
    ],
    DataCategory.DIAGNOSES: [
        "the diagnosis history",
        "the full problem list",
        "the list of current conditions",
    ],
    DataCategory.MEDICATIONS: [
        "the current medication list",
        "the active prescriptions",
        "the drug history",
    ],
    DataCategory.LAB_RESULTS: [
        "the recent lab results",
        "the latest blood test values",
        "the laboratory panel",
    ],
    DataCategory.IMAGING: [
        "the radiology images",
        "the recent MRI scan",
        "the chest X-ray",
    ],
    DataCategory.GENETIC: [
        "the genetic test results",
        "the genomic profile",
        "the hereditary risk markers",
    ],
    DataCategory.MENTAL_HEALTH: [
        "the mental health notes",
        "the psychiatric history",
        "the therapy session records",
    ],
    DataCategory.BILLING: [
        "the billing record",
        "the invoice and charge history",
        "the itemised statement",
    ],
}

ALL_CATEGORIES = list(CATEGORY_PHRASES.keys())


def _join(parts: list[str]) -> str:
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def make_request_text(
    purpose: Purpose, categories: list[DataCategory], rng: np.random.Generator
) -> str:
    opener = rng.choice(PURPOSE_PHRASES[purpose])
    phrases = [str(rng.choice(CATEGORY_PHRASES[c])) for c in categories]
    return f"{opener} {_join(phrases)}."


def make_dataset(n: int = 1200, seed: int = 13) -> tuple[list[str], list[int], np.ndarray]:
    """Return (texts, purpose labels, category-mask matrix) for training.

    The matrix has one column per category (in ``ALL_CATEGORIES`` order) with a
    1 where the request asks for that category.
    """
    rng = np.random.default_rng(seed)
    purposes = list(Purpose)
    texts: list[str] = []
    y_purpose: list[int] = []
    y_cat = np.zeros((n, len(ALL_CATEGORIES)), dtype=int)

    for i in range(n):
        purpose = purposes[int(rng.integers(len(purposes)))]
        k = int(rng.integers(1, 4))  # 1..3 categories
        chosen = list(rng.choice(ALL_CATEGORIES, size=k, replace=False))
        texts.append(make_request_text(purpose, chosen, rng))
        y_purpose.append(int(purpose))
        for c in chosen:
            y_cat[i, ALL_CATEGORIES.index(c)] = 1

    return texts, y_purpose, y_cat
