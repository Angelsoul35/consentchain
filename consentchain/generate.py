"""Synthetic, labelled health-data access requests for training and evaluation.

A classifier trained and tested on a handful of templates memorises them and
reports a meaningless ~1.0 accuracy. To avoid that trap this generator uses many
phrasings per purpose and per data category, with natural synonyms ("bloodwork",
"genome", "diagnosis codes"), and it can split the *phrasings themselves* into
disjoint train/test pools (:func:`make_split_datasets`) so evaluation measures
generalisation to unseen wording, not recall of seen templates.

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
        "the attending doctor is reviewing the case and needs",
        "to make a treatment decision we request",
        "the oncologist must see",
        "for the surgical plan the team needs",
        "to manage the patient's condition we need",
        "the specialist treating this patient asks for",
    ],
    Purpose.PAYMENT: [
        "the billing department needs",
        "to process the insurance claim we require",
        "for reimbursement, please provide",
        "to verify coverage we request",
        "the payer is auditing the claim and needs",
        "to settle the outstanding invoice we need",
        "our actuary needs",
        "to adjudicate the claim the insurer requests",
        "for the co-payment calculation we need",
        "the finance office needs for billing",
    ],
    Purpose.OPERATIONS: [
        "for a quality-of-care audit we need",
        "the compliance review requires",
        "for internal care-coordination we request",
        "to improve our service we are reviewing",
        "the operations team needs",
        "for an accreditation review, please share",
        "for a service-quality audit we are examining",
        "to coordinate the care pathway we need",
        "the clinical governance committee requires",
        "for workflow analysis we need",
    ],
    Purpose.RESEARCH: [
        "for an approved research study we request",
        "the clinical trial protocol requires",
        "for an epidemiological analysis we need",
        "the research cohort needs",
        "under the study's ethics approval we request",
        "for a registered research project, please provide",
        "the ethics board approved a study using",
        "for a longitudinal study we are collecting",
        "the principal investigator requests",
        "for the trial's secondary endpoint we need",
    ],
}

# Each category's phrasings deliberately share a recurring stem (demographic,
# diagnos, medication/drug, lab/blood, imaging/scan, genetic/genom, mental/
# psychiatric, billing/invoice) so that character n-grams still recognise a
# held-out phrasing from the stem it shares with the training ones.
CATEGORY_PHRASES: dict[DataCategory, list[str]] = {
    DataCategory.DEMOGRAPHICS: [
        "the patient's demographic details",
        "the demographic and contact information",
        "the basic demographic record",
        "the demographic identifiers and age",
        "the demographic registration fields",
        "the demographic data on file",
    ],
    DataCategory.DIAGNOSES: [
        "the diagnosis history",
        "the list of diagnoses and conditions",
        "the recorded diagnosis codes",
        "the diagnosis and problem list",
        "the diagnoses and comorbidities",
        "the current diagnosis record",
    ],
    DataCategory.MEDICATIONS: [
        "the current medication list",
        "the active medication and drug record",
        "the medication and prescription history",
        "the list of medications and dosages",
        "the medication dispensing record",
        "the prescribed medication details",
    ],
    DataCategory.LAB_RESULTS: [
        "the recent lab results",
        "the latest blood lab values",
        "the laboratory test panel",
        "the lab and bloodwork results",
        "the pathology lab reports",
        "the laboratory result record",
    ],
    DataCategory.IMAGING: [
        "the radiology imaging studies",
        "the recent MRI imaging scan",
        "the imaging and scan reports",
        "the CT imaging studies",
        "the ultrasound imaging scan",
        "the diagnostic imaging record",
    ],
    DataCategory.GENETIC: [
        "the genetic test results",
        "the genomic sequencing profile",
        "the genetic and hereditary markers",
        "the patient's genome sequence",
        "the genetic variant report",
        "the inherited genetic data",
    ],
    DataCategory.MENTAL_HEALTH: [
        "the mental health notes",
        "the psychiatric and mental health history",
        "the mental health therapy records",
        "the behavioural and mental health assessment",
        "the psychiatric evaluation notes",
        "the mental health counselling record",
    ],
    DataCategory.BILLING: [
        "the billing record",
        "the billing invoice and charge history",
        "the itemised billing statement",
        "the billing account and payments",
        "the billing superbill and claim lines",
        "the billing and charge details",
    ],
}

# Short trailing clauses heavy in *recurring* purpose vocabulary. These spread the
# purpose signal across many words (treat/therapy/clinical, claim/reimbursement/
# coverage, audit/compliance/quality, study/trial/research) so a held-out opener
# still carries signal the model saw elsewhere — the key to real generalisation.
PURPOSE_CONTEXTS: dict[Purpose, list[str]] = {
    Purpose.TREATMENT: [
        "for treatment purposes",
        "to guide clinical care",
        "to manage the patient's therapy",
        "for the clinical treatment plan",
    ],
    Purpose.PAYMENT: [
        "to process the claim",
        "for reimbursement of the invoice",
        "to verify insurance coverage",
        "for the billing and payment record",
    ],
    Purpose.OPERATIONS: [
        "for the quality audit",
        "for compliance and governance",
        "for internal care coordination",
        "to review service quality",
    ],
    Purpose.RESEARCH: [
        "for the research study",
        "under the trial protocol",
        "for the research cohort analysis",
        "for the approved study",
    ],
}

ALL_CATEGORIES = list(CATEGORY_PHRASES.keys())


def _join(parts: list[str]) -> str:
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def _compose(opener: str, body: str, context: str, rng: np.random.Generator) -> str:
    # Structural variety so phrasing, not just word choice, varies.
    shape = int(rng.integers(3))
    if shape == 0:
        return f"{opener} {body} {context}."
    if shape == 1:
        return f"{opener[0].upper()}{opener[1:]} {body}, {context}."
    return f"{context.capitalize()}: {opener} {body}."


def _generate(
    rng: np.random.Generator,
    n: int,
    purpose_pool: dict[Purpose, list[str]],
    category_pool: dict[DataCategory, list[str]],
    context_pool: dict[Purpose, list[str]],
) -> tuple[list[str], list[int], np.ndarray]:
    purposes = list(Purpose)
    texts: list[str] = []
    y_purpose: list[int] = []
    y_cat = np.zeros((n, len(ALL_CATEGORIES)), dtype=int)
    for i in range(n):
        purpose = purposes[int(rng.integers(len(purposes)))]
        k = int(rng.integers(1, 4))
        chosen = list(rng.choice(ALL_CATEGORIES, size=k, replace=False))
        opener = str(rng.choice(purpose_pool[purpose]))
        context = str(rng.choice(context_pool[purpose]))
        phrases = [str(rng.choice(category_pool[c])) for c in chosen]
        texts.append(_compose(opener, _join(phrases), context, rng))
        y_purpose.append(int(purpose))
        for c in chosen:
            y_cat[i, ALL_CATEGORIES.index(c)] = 1
    return texts, y_purpose, y_cat


def make_dataset(n: int = 1600, seed: int = 13) -> tuple[list[str], list[int], np.ndarray]:
    """Return (texts, purpose labels, category-mask matrix) using all phrasings."""
    rng = np.random.default_rng(seed)
    return _generate(rng, n, PURPOSE_PHRASES, CATEGORY_PHRASES, PURPOSE_CONTEXTS)


def _split_pool(pool: dict, rng: np.random.Generator, holdout_frac: float):
    train, test = {}, {}
    for key, phrases in pool.items():
        idx = rng.permutation(len(phrases))
        cut = max(1, round(len(phrases) * (1 - holdout_frac)))
        train[key] = [phrases[i] for i in idx[:cut]]
        test[key] = [phrases[i] for i in idx[cut:]] or [phrases[idx[-1]]]
    return train, test


def make_split_datasets(
    n: int = 1600, seed: int = 13, holdout_frac: float = 0.4
):
    """Phrase-disjoint train/test: test sentences use phrasings unseen in training.

    Returns (train_texts, train_yp, train_yc, test_texts, test_yp, test_yc).
    """
    rng = np.random.default_rng(seed)
    p_train, p_test = _split_pool(PURPOSE_PHRASES, rng, holdout_frac)
    c_train, c_test = _split_pool(CATEGORY_PHRASES, rng, holdout_frac)
    ctx_train, ctx_test = _split_pool(PURPOSE_CONTEXTS, rng, holdout_frac)
    tr = _generate(rng, n, p_train, c_train, ctx_train)
    te = _generate(rng, n // 3, p_test, c_test, ctx_test)
    return (*tr, *te)
