"""Decide whether an access request is allowed by the patient's on-chain consent.

The classifier turns a request into a purpose and a set of categories. This layer
reads the patient's consent for that requester and purpose from the registry and
decides: ALLOW, DENY, or REVIEW. The decision is purpose-scoped (consent given
for treatment does not authorise research) and category-exact (every requested
category must be covered). Low classifier confidence routes the request to a
human, and any missing *sensitive* category is always a hard denial.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .chain.registry import RegistryClient, party_id
from .classifier import ClassifiedRequest
from .scopes import SENSITIVE, category_names


class Decision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REVIEW = "review"


@dataclass
class AccessOutcome:
    decision: Decision
    purpose: str
    requested_categories: list[str]
    missing_categories: list[str]
    reasons: list[str]
    confidence: float
    contract_address: str


def evaluate(
    registry: RegistryClient,
    patient_handle: str,
    requester_handle: str,
    classified: ClassifiedRequest,
    min_confidence: float,
) -> AccessOutcome:
    patient = party_id(patient_handle)
    requester = party_id(requester_handle)
    purpose = classified.purpose
    requested_mask = classified.category_mask

    consent = registry.consent_of(patient, requester, int(purpose))
    granted_mask = consent.category_mask if consent.on_record else 0
    missing_mask = requested_mask & ~granted_mask

    reasons: list[str] = []

    if classified.purpose_confidence < min_confidence:
        reasons.append(
            f"classifier confidence {classified.purpose_confidence:.2f} is below the "
            f"{min_confidence:.2f} threshold; routed to a human reviewer"
        )
        return _outcome(
            Decision.REVIEW, classified, requested_mask, missing_mask, reasons, registry.address
        )

    on_chain_ok = registry.has_consent(patient, requester, int(purpose), requested_mask)

    if on_chain_ok:
        reasons.append(
            f"patient consent for {purpose.label.lower()} covers all requested categories "
            f"and is still valid (version {consent.version})"
        )
        return _outcome(Decision.ALLOW, classified, requested_mask, 0, reasons, registry.address)

    if not consent.on_record:
        reasons.append(f"no consent on record for {purpose.label.lower()}")
    elif missing_mask:
        reasons.append("consent does not cover: " + ", ".join(category_names(missing_mask)))
    else:
        reasons.append("consent has expired")

    sensitive_missing = missing_mask & int(SENSITIVE)
    if sensitive_missing:
        reasons.append(
            "request touches sensitive categories without consent: "
            + ", ".join(category_names(sensitive_missing))
        )

    return _outcome(
        Decision.DENY, classified, requested_mask, missing_mask, reasons, registry.address
    )


def _outcome(
    decision: Decision,
    classified: ClassifiedRequest,
    requested_mask: int,
    missing_mask: int,
    reasons: list[str],
    address: str,
) -> AccessOutcome:
    return AccessOutcome(
        decision=decision,
        purpose=classified.purpose.label,
        requested_categories=category_names(requested_mask),
        missing_categories=category_names(missing_mask),
        reasons=reasons,
        confidence=classified.purpose_confidence,
        contract_address=address,
    )
