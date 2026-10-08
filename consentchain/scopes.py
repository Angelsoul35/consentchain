"""The consent vocabulary: purposes and data categories.

A consent record answers: *for which purpose*, and *which categories of data*,
has a patient allowed a requester to use. Purposes mirror the familiar
treatment / payment / operations split, plus research. Categories are the kinds
of clinical data a request can touch. On-chain, categories are packed into a
16-bit mask (one bit per category) so a whole consent scope is a single integer.
"""

from __future__ import annotations

from enum import IntEnum, IntFlag


class Purpose(IntEnum):
    """Why a requester wants the data. Small integer codes, stored on-chain."""

    TREATMENT = 0
    PAYMENT = 1
    OPERATIONS = 2
    RESEARCH = 3

    @property
    def label(self) -> str:
        return self.name.title()


class DataCategory(IntFlag):
    """Kinds of clinical data. Each is one bit of the on-chain category mask."""

    DEMOGRAPHICS = 1 << 0
    DIAGNOSES = 1 << 1
    MEDICATIONS = 1 << 2
    LAB_RESULTS = 1 << 3
    IMAGING = 1 << 4
    GENETIC = 1 << 5
    MENTAL_HEALTH = 1 << 6
    BILLING = 1 << 7


# Categories that are extra-sensitive. Research consent for these should be
# explicit; the policy layer treats a mismatch here as a hard denial, never a
# "near miss".
SENSITIVE = DataCategory.GENETIC | DataCategory.MENTAL_HEALTH


def categories_to_mask(categories: list[DataCategory] | DataCategory) -> int:
    """Pack one or more categories into the 16-bit on-chain mask."""
    if isinstance(categories, DataCategory):
        return int(categories)
    mask = 0
    for category in categories:
        mask |= int(category)
    return mask


def mask_to_categories(mask: int) -> list[DataCategory]:
    """Unpack a mask into its categories, in a stable order."""
    return [c for c in DataCategory if mask & int(c)]


def category_names(mask: int) -> list[str]:
    """Human-readable names for the categories in a mask."""
    return [c.name.lower() for c in mask_to_categories(mask)]
