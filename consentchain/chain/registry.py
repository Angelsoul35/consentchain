"""Registry clients: a Web3-backed client and an in-memory fake.

Both implement :class:`RegistryClient`, so the service can record and check
consent against the real compiled contract (on Anvil or an in-memory PyEVM node)
or against an in-memory fake with the same behaviour. Patients and requesters are
identified by a bytes32 id (a hash of a stable handle), so no identities reach
the chain.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from eth_utils import keccak
from web3 import Web3
from web3.contract import Contract

from .artifacts import contract_abi, contract_bytecode


def party_id(handle: str) -> bytes:
    """Return the 32-byte on-chain id for a patient or requester handle."""
    return keccak(text=handle)


@dataclass(frozen=True)
class Consent:
    category_mask: int
    expiry: int
    version: int

    @property
    def on_record(self) -> bool:
        return self.version > 0 and self.category_mask != 0


@runtime_checkable
class RegistryClient(Protocol):
    @property
    def address(self) -> str: ...

    def grant(
        self, patient: bytes, requester: bytes, purpose: int, category_mask: int, expiry: int
    ) -> int: ...

    def revoke(self, patient: bytes, requester: bytes, purpose: int) -> int: ...

    def consent_of(self, patient: bytes, requester: bytes, purpose: int) -> Consent: ...

    def has_consent(
        self, patient: bytes, requester: bytes, purpose: int, required_mask: int
    ) -> bool: ...


class InMemoryRegistryClient:
    """A dict-backed registry that mirrors the contract's accounting."""

    def __init__(self) -> None:
        self._consents: dict[tuple[bytes, bytes, int], list[int]] = {}
        self.total_grants = 0
        self.total_revocations = 0

    @property
    def address(self) -> str:
        return "0x0000000000000000000000000000000000000000"

    def _record(self, key: tuple[bytes, bytes, int]) -> list[int]:
        return self._consents.setdefault(key, [0, 0, 0])  # mask, expiry, version

    def grant(self, patient, requester, purpose, category_mask, expiry) -> int:
        if patient == bytes(32) or requester == bytes(32):
            raise ValueError("zero party")
        if category_mask == 0:
            raise ValueError("empty scope")
        if expiry <= int(time.time()):
            raise ValueError("past expiry")
        rec = self._record((patient, requester, purpose))
        rec[0] = category_mask
        rec[1] = expiry
        rec[2] += 1
        self.total_grants += 1
        return rec[2]

    def revoke(self, patient, requester, purpose) -> int:
        rec = self._record((patient, requester, purpose))
        rec[0] = 0
        rec[1] = 0
        rec[2] += 1
        self.total_revocations += 1
        return rec[2]

    def consent_of(self, patient, requester, purpose) -> Consent:
        rec = self._consents.get((patient, requester, purpose), [0, 0, 0])
        return Consent(category_mask=rec[0], expiry=rec[1], version=rec[2])

    def has_consent(self, patient, requester, purpose, required_mask) -> bool:
        rec = self._consents.get((patient, requester, purpose), [0, 0, 0])
        if rec[1] <= int(time.time()):
            return False
        return (rec[0] & required_mask) == required_mask


def deploy_registry(w3: Web3, deployer: str, private_key: str | None = None) -> str:
    deployer = Web3.to_checksum_address(deployer)
    factory = w3.eth.contract(abi=contract_abi(), bytecode=contract_bytecode())
    if private_key:
        tx = factory.constructor().build_transaction(
            {"from": deployer, "nonce": w3.eth.get_transaction_count(deployer)}
        )
        signed = w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    else:
        tx_hash = factory.constructor().transact({"from": deployer})
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return receipt["contractAddress"]


class Web3RegistryClient:
    def __init__(
        self, w3: Web3, contract_address: str, account: str, private_key: str | None = None
    ) -> None:
        self._w3 = w3
        self._account = Web3.to_checksum_address(account)
        self._private_key = private_key
        self._contract: Contract = w3.eth.contract(
            address=Web3.to_checksum_address(contract_address), abi=contract_abi()
        )

    @property
    def address(self) -> str:
        return self._contract.address

    def _send(self, fn) -> None:
        if self._private_key:
            tx = fn.build_transaction(
                {"from": self._account, "nonce": self._w3.eth.get_transaction_count(self._account)}
            )
            signed = self._w3.eth.account.sign_transaction(tx, self._private_key)
            tx_hash = self._w3.eth.send_raw_transaction(signed.raw_transaction)
        else:
            tx_hash = fn.transact({"from": self._account})
        self._w3.eth.wait_for_transaction_receipt(tx_hash)

    def grant(self, patient, requester, purpose, category_mask, expiry) -> int:
        self._send(
            self._contract.functions.grant(patient, requester, purpose, category_mask, expiry)
        )
        return self.consent_of(patient, requester, purpose).version

    def revoke(self, patient, requester, purpose) -> int:
        self._send(self._contract.functions.revoke(patient, requester, purpose))
        return self.consent_of(patient, requester, purpose).version

    def consent_of(self, patient, requester, purpose) -> Consent:
        mask, expiry, version = self._contract.functions.consentOf(
            patient, requester, purpose
        ).call()
        return Consent(category_mask=int(mask), expiry=int(expiry), version=int(version))

    def has_consent(self, patient, requester, purpose, required_mask) -> bool:
        return bool(
            self._contract.functions.hasConsent(patient, requester, purpose, required_mask).call()
        )
