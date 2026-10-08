from __future__ import annotations

from consentchain.scopes import (
    SENSITIVE,
    DataCategory,
    Purpose,
    categories_to_mask,
    category_names,
    mask_to_categories,
)


def test_mask_round_trip():
    cats = [DataCategory.DIAGNOSES, DataCategory.LAB_RESULTS, DataCategory.GENETIC]
    mask = categories_to_mask(cats)
    assert mask_to_categories(mask) == cats
    assert set(category_names(mask)) == {"diagnoses", "lab_results", "genetic"}


def test_single_category_mask():
    assert categories_to_mask(DataCategory.BILLING) == int(DataCategory.BILLING)


def test_sensitive_set():
    assert SENSITIVE & int(DataCategory.GENETIC)
    assert SENSITIVE & int(DataCategory.MENTAL_HEALTH)
    assert not SENSITIVE & int(DataCategory.DEMOGRAPHICS)


def test_purpose_labels():
    assert Purpose.TREATMENT.label == "Treatment"
    assert Purpose(3) is Purpose.RESEARCH
