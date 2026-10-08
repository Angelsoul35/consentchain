"""Tie the pieces together: classify a request, check consent, record consent."""

from __future__ import annotations

import time
from dataclasses import asdict

from .chain.registry import (
    InMemoryRegistryClient,
    RegistryClient,
    party_id,
)
from .classifier import RequestClassifier
from .config import Settings, get_settings
from .policy import AccessOutcome, evaluate
from .scopes import DataCategory, Purpose, categories_to_mask


class ConsentService:
    def __init__(
        self,
        settings: Settings | None = None,
        registry: RegistryClient | None = None,
        classifier: RequestClassifier | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.classifier = classifier or RequestClassifier().fit()
        self.registry = registry if registry is not None else self._build_registry()

    def _build_registry(self) -> RegistryClient:
        if (
            self.settings.chain_enabled
            and self.settings.contract_address
            and self.settings.chain_private_key
        ):
            from web3 import Web3

            from .chain.registry import Web3RegistryClient

            w3 = Web3(Web3.HTTPProvider(self.settings.chain_rpc_url))
            account = w3.eth.account.from_key(self.settings.chain_private_key).address
            return Web3RegistryClient(
                w3, self.settings.contract_address, account, self.settings.chain_private_key
            )
        return InMemoryRegistryClient()

    def grant_consent(
        self,
        patient_handle: str,
        requester_handle: str,
        purpose: Purpose,
        categories: list[DataCategory],
        ttl_days: int = 365,
    ) -> dict:
        expiry = int(time.time()) + ttl_days * 86400
        mask = categories_to_mask(categories)
        version = self.registry.grant(
            party_id(patient_handle), party_id(requester_handle), int(purpose), mask, expiry
        )
        return {
            "patient": patient_handle,
            "requester": requester_handle,
            "purpose": purpose.label,
            "categories": [c.name.lower() for c in categories],
            "expiry": expiry,
            "version": version,
            "contract_address": self.registry.address,
        }

    def revoke_consent(self, patient_handle: str, requester_handle: str, purpose: Purpose) -> dict:
        version = self.registry.revoke(
            party_id(patient_handle), party_id(requester_handle), int(purpose)
        )
        return {
            "patient": patient_handle,
            "requester": requester_handle,
            "purpose": purpose.label,
            "version": version,
            "contract_address": self.registry.address,
        }

    def evaluate_request(self, patient_handle: str, requester_handle: str, text: str) -> dict:
        classified = self.classifier.classify(text)
        outcome: AccessOutcome = evaluate(
            self.registry,
            patient_handle,
            requester_handle,
            classified,
            self.settings.min_confidence,
        )
        result = asdict(outcome)
        result["decision"] = outcome.decision.value
        result["classified_purpose"] = classified.purpose.label
        result["top_terms"] = classified.top_terms
        return result
