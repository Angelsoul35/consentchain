from __future__ import annotations

import pytest
from web3 import EthereumTesterProvider, Web3

from consentchain.chain.registry import (
    InMemoryRegistryClient,
    Web3RegistryClient,
    deploy_registry,
)
from consentchain.classifier import RequestClassifier
from consentchain.config import Settings
from consentchain.service import ConsentService


@pytest.fixture(scope="session")
def classifier() -> RequestClassifier:
    # Fit once and share across tests; fitting is deterministic.
    return RequestClassifier().fit()


@pytest.fixture
def w3() -> Web3:
    return Web3(EthereumTesterProvider())


@pytest.fixture
def chain_registry(w3) -> Web3RegistryClient:
    operator = w3.eth.accounts[0]
    return Web3RegistryClient(w3, deploy_registry(w3, operator), operator)


@pytest.fixture
def settings() -> Settings:
    return Settings(chain_enabled=False, min_confidence=0.55)


@pytest.fixture
def service(settings, classifier) -> ConsentService:
    return ConsentService(
        settings=settings, registry=InMemoryRegistryClient(), classifier=classifier
    )
