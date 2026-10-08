from __future__ import annotations

import time

from consentchain.chain.registry import InMemoryRegistryClient, party_id
from consentchain.classifier import ClassifiedRequest
from consentchain.policy import Decision, evaluate
from consentchain.scopes import DataCategory, Purpose, categories_to_mask


def _request(purpose, categories, confidence=0.99) -> ClassifiedRequest:
    mask = categories_to_mask(categories)
    return ClassifiedRequest(
        purpose=purpose,
        purpose_confidence=confidence,
        category_mask=mask,
        category_names=[c.name.lower() for c in categories],
    )


def _grant(reg, patient, requester, purpose, categories, ttl_days=30):
    reg.grant(
        party_id(patient),
        party_id(requester),
        int(purpose),
        categories_to_mask(categories),
        int(time.time()) + ttl_days * 86400,
    )


def test_allow_when_consent_covers_request():
    reg = InMemoryRegistryClient()
    _grant(reg, "p", "r", Purpose.TREATMENT, [DataCategory.DIAGNOSES, DataCategory.MEDICATIONS])
    req = _request(Purpose.TREATMENT, [DataCategory.DIAGNOSES])
    outcome = evaluate(reg, "p", "r", req, min_confidence=0.55)
    assert outcome.decision is Decision.ALLOW
    assert outcome.missing_categories == []


def test_deny_when_category_not_consented():
    reg = InMemoryRegistryClient()
    _grant(reg, "p", "r", Purpose.TREATMENT, [DataCategory.DIAGNOSES])
    req = _request(Purpose.TREATMENT, [DataCategory.DIAGNOSES, DataCategory.IMAGING])
    outcome = evaluate(reg, "p", "r", req, min_confidence=0.55)
    assert outcome.decision is Decision.DENY
    assert "imaging" in outcome.missing_categories


def test_deny_when_no_consent_for_purpose():
    reg = InMemoryRegistryClient()
    _grant(reg, "p", "r", Purpose.TREATMENT, [DataCategory.DIAGNOSES])
    # Consent exists for treatment, but this is a research request.
    req = _request(Purpose.RESEARCH, [DataCategory.DIAGNOSES])
    outcome = evaluate(reg, "p", "r", req, min_confidence=0.55)
    assert outcome.decision is Decision.DENY
    assert any("no consent on record" in r for r in outcome.reasons)


def test_review_when_confidence_low():
    reg = InMemoryRegistryClient()
    _grant(reg, "p", "r", Purpose.TREATMENT, [DataCategory.DIAGNOSES])
    req = _request(Purpose.TREATMENT, [DataCategory.DIAGNOSES], confidence=0.40)
    outcome = evaluate(reg, "p", "r", req, min_confidence=0.55)
    assert outcome.decision is Decision.REVIEW


def test_deny_when_consent_expired():
    reg = InMemoryRegistryClient()
    _grant(reg, "p", "r", Purpose.TREATMENT, [DataCategory.DIAGNOSES])
    # Force the stored record to be expired.
    key = (party_id("p"), party_id("r"), int(Purpose.TREATMENT))
    reg._consents[key][1] = int(time.time()) - 10
    req = _request(Purpose.TREATMENT, [DataCategory.DIAGNOSES])
    outcome = evaluate(reg, "p", "r", req, min_confidence=0.55)
    assert outcome.decision is Decision.DENY
    assert any("expired" in r for r in outcome.reasons)


def test_sensitive_missing_is_flagged():
    reg = InMemoryRegistryClient()
    _grant(reg, "p", "r", Purpose.RESEARCH, [DataCategory.DIAGNOSES])
    req = _request(Purpose.RESEARCH, [DataCategory.DIAGNOSES, DataCategory.GENETIC])
    outcome = evaluate(reg, "p", "r", req, min_confidence=0.55)
    assert outcome.decision is Decision.DENY
    assert any("sensitive" in r for r in outcome.reasons)
    assert "genetic" in outcome.missing_categories
