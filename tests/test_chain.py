from __future__ import annotations

import time

import pytest
from eth_tester.exceptions import TransactionFailed
from web3.exceptions import ContractLogicError

from consentchain.chain.registry import (
    InMemoryRegistryClient,
    Web3RegistryClient,
    deploy_registry,
    party_id,
)
from consentchain.scopes import DataCategory, Purpose, categories_to_mask

pytestmark = pytest.mark.chain

REVERT_ERRORS = (ContractLogicError, TransactionFailed)


def _future(days=30) -> int:
    return int(time.time()) + days * 86400


def test_grant_and_check_consent(chain_registry):
    patient, requester = party_id("alice"), party_id("clinic")
    mask = categories_to_mask([DataCategory.DIAGNOSES, DataCategory.MEDICATIONS])
    version = chain_registry.grant(patient, requester, int(Purpose.TREATMENT), mask, _future())
    assert version == 1

    stored = chain_registry.consent_of(patient, requester, int(Purpose.TREATMENT))
    assert stored.category_mask == mask
    assert stored.on_record

    # covers a subset
    assert chain_registry.has_consent(
        patient, requester, int(Purpose.TREATMENT), categories_to_mask([DataCategory.DIAGNOSES])
    )
    # does not cover an un-consented category
    assert not chain_registry.has_consent(
        patient, requester, int(Purpose.TREATMENT), categories_to_mask([DataCategory.IMAGING])
    )
    # purpose is scoped: no consent for research
    assert not chain_registry.has_consent(patient, requester, int(Purpose.RESEARCH), mask)


def test_revoke_clears_consent(chain_registry):
    patient, requester = party_id("alice"), party_id("clinic")
    mask = categories_to_mask([DataCategory.DIAGNOSES])
    chain_registry.grant(patient, requester, int(Purpose.TREATMENT), mask, _future())
    chain_registry.revoke(patient, requester, int(Purpose.TREATMENT))
    assert not chain_registry.has_consent(patient, requester, int(Purpose.TREATMENT), mask)
    stored = chain_registry.consent_of(patient, requester, int(Purpose.TREATMENT))
    assert stored.category_mask == 0
    assert stored.version == 2  # grant then revoke


def test_only_operator_can_grant(w3):
    owner, outsider = w3.eth.accounts[0], w3.eth.accounts[1]
    address = deploy_registry(w3, owner)
    rogue = Web3RegistryClient(w3, address, outsider)
    with pytest.raises(REVERT_ERRORS):
        rogue.grant(party_id("a"), party_id("b"), 0, 1, _future())


def test_grant_rejects_empty_scope(chain_registry):
    with pytest.raises(REVERT_ERRORS):
        chain_registry.grant(party_id("a"), party_id("b"), 0, 0, _future())


def test_grant_rejects_past_expiry(chain_registry):
    with pytest.raises(REVERT_ERRORS):
        chain_registry.grant(party_id("a"), party_id("b"), 0, 1, int(time.time()) - 10)


def test_in_memory_matches_contract(chain_registry):
    patient, requester = party_id("x"), party_id("y")
    mask = categories_to_mask([DataCategory.LAB_RESULTS, DataCategory.BILLING])
    expiry = _future()

    mem = InMemoryRegistryClient()
    v_chain = chain_registry.grant(patient, requester, int(Purpose.PAYMENT), mask, expiry)
    v_mem = mem.grant(patient, requester, int(Purpose.PAYMENT), mask, expiry)
    assert v_chain == v_mem

    c_chain = chain_registry.consent_of(patient, requester, int(Purpose.PAYMENT))
    c_mem = mem.consent_of(patient, requester, int(Purpose.PAYMENT))
    assert c_chain.category_mask == c_mem.category_mask
    assert c_chain.version == c_mem.version
    assert chain_registry.has_consent(
        patient, requester, int(Purpose.PAYMENT), mask
    ) == mem.has_consent(patient, requester, int(Purpose.PAYMENT), mask)
