"""ConsentChain command-line demo."""

from __future__ import annotations

import argparse

from web3 import EthereumTesterProvider, Web3

from .chain.registry import Web3RegistryClient, deploy_registry
from .config import get_settings
from .scopes import DataCategory, Purpose
from .service import ConsentService


def demo() -> None:
    settings = get_settings()

    print("1) Deploying ConsentRegistry to an in-memory EVM ...")
    w3 = Web3(EthereumTesterProvider())
    operator = w3.eth.accounts[0]
    address = deploy_registry(w3, operator)
    registry = Web3RegistryClient(w3, address, operator)
    print(f"   registry at {address}")

    service = ConsentService(settings=settings, registry=registry)

    print("2) Patient grants a care team consent for treatment ...")
    grant = service.grant_consent(
        "patient:alice",
        "clinic:oncology",
        Purpose.TREATMENT,
        [DataCategory.DIAGNOSES, DataCategory.MEDICATIONS, DataCategory.LAB_RESULTS],
        ttl_days=180,
    )
    print(f"   granted {grant['categories']} for {grant['purpose']} (version {grant['version']})")

    print("3) An in-scope treatment request:")
    text1 = (
        "The treating physician needs the recent lab results and the current "
        "medication list to adjust the patient's therapy."
    )
    out1 = service.evaluate_request("patient:alice", "clinic:oncology", text1)
    print(f'   "{text1}"')
    print(f"   -> {out1['decision'].upper()} ({out1['classified_purpose']}); {out1['reasons'][0]}")

    print("4) A research request with no consent on record:")
    text2 = (
        "For an approved research study we request the patient's genetic test "
        "results and the full problem list."
    )
    out2 = service.evaluate_request("patient:alice", "clinic:oncology", text2)
    print(f'   "{text2}"')
    print(f"   -> {out2['decision'].upper()} ({out2['classified_purpose']})")
    for reason in out2["reasons"]:
        print(f"      - {reason}")

    print("5) Patient revokes the treatment consent:")
    rev = service.revoke_consent("patient:alice", "clinic:oncology", Purpose.TREATMENT)
    print(f"   revoked (version {rev['version']})")
    out3 = service.evaluate_request("patient:alice", "clinic:oncology", text1)
    print(f"   same treatment request now -> {out3['decision'].upper()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="ConsentChain CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo", help="deploy, grant consent, and evaluate access requests")
    args = parser.parse_args()
    if args.command == "demo":
        demo()


if __name__ == "__main__":
    main()
