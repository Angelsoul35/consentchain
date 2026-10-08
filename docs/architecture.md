# Architecture

ConsentChain reads a plain-language health-data access request, turns it into a
structured claim, and checks that claim against a patient's on-chain consent.
This document describes the pieces, how data flows through them, and the
boundaries between them.

## The pieces

| Layer          | Module                            | Responsibility                                               |
| -------------- | --------------------------------- | ------------------------------------------------------------ |
| Vocabulary     | `consentchain/scopes.py`          | Purposes, data categories, and the category bitmask          |
| Data           | `consentchain/generate.py`        | Synthetic, labelled access requests for training             |
| Classifier     | `consentchain/classifier.py`      | Request text → purpose + categories + explanation            |
| Policy         | `consentchain/policy.py`          | Decide allow / deny / review against the consent on record   |
| Orchestration  | `consentchain/service.py`         | Grant, revoke, and evaluate requests end to end              |
| Registry client| `consentchain/chain/registry.py`  | Talk to the contract (or an in-memory fake)                  |
| Artifacts      | `consentchain/chain/artifacts.py` | Load the committed ABI + bytecode                            |
| Compiler       | `consentchain/chain/compile.py`   | Build the artifact from Solidity via `solc-js`               |
| Contract       | `contracts/src/ConsentRegistry.sol`| Store consent and its history on-chain                      |
| HTTP API       | `consentchain/main.py`            | Expose grant / revoke / evaluate over REST                   |
| CLI            | `consentchain/cli.py`             | End-to-end demo against an in-memory EVM                     |

## Data flow for one request

```
┌────────────────────┐   classify()   ┌────────────────────┐
│  request text      │ ─────────────▶ │ ClassifiedRequest  │
│ (free language)    │                 │ purpose, mask,     │
└────────────────────┘                 │ confidence, terms  │
                                        └─────────┬──────────┘
                                                  │  evaluate(...)
                                                  ▼
                        ┌─────────────────────────────────────────┐
                        │ registry.consent_of / has_consent         │
                        │ (ConsentRegistry on-chain)                │
                        └─────────────────────┬─────────────────────┘
                                              ▼
                                   ┌────────────────────┐
                                   │ AccessOutcome      │
                                   │ allow/deny/review  │
                                   │ + reasons          │
                                   └────────────────────┘
```

1. The classifier turns the request into a `ClassifiedRequest`: a purpose, a
   category mask, a confidence, and the words that drove the purpose decision.
2. The policy layer reads the patient's consent for that `(requester, purpose)`
   pair from the registry and compares the requested categories against the
   granted ones.
3. The result is an `AccessOutcome` with a decision and human-readable reasons.

## The consent model

A consent record is keyed by the triple `(patient, requester, purpose)` and
stores:

- a **category mask** — a 16-bit integer, one bit per data category;
- an **expiry** — Unix seconds, after which the consent is invalid;
- a **version** — incremented on every grant or revoke.

This shape makes the three rules cheap to enforce. *Purpose-scoped*: a different
purpose is a different key. *Category-exact*: `granted & requested == requested`.
*Time-bound*: `expiry > now`.

## Why a classifier and a policy, kept apart

The classifier answers a language question — "what is this request asking for?"
— and nothing else. The policy answers a governance question — "is that allowed
right now?" — and nothing else. Keeping them apart means:

- The classifier can be retrained or replaced without touching the rules.
- The policy is pure, deterministic, and easy to audit line by line.
- A low-confidence classification becomes a **review**, not a guess, because the
  policy, not the model, owns the final decision.

## The registry boundary

`RegistryClient` is a `Protocol` with two implementations:

- **`Web3RegistryClient`** talks to a deployed `ConsentRegistry` over JSON-RPC
  and signs transactions when given a private key.
- **`InMemoryRegistryClient`** mirrors the contract's accounting in a dictionary,
  with the same guards (zero party, empty scope, past expiry).

Because both satisfy the same protocol, the service, the API, and the tests do
not care which is behind them. A dedicated test grants the same consent on both
the real contract and the fake and asserts they agree, so the fake cannot drift.

## Privacy

Nothing that could identify a patient or reveal a diagnosis is written on-chain.
A patient and a requester are each a `bytes32` id (the keccak hash of a stable
handle). Data categories are bit positions and purposes are small integers. The
mapping from a real identity to a handle stays off-chain, under the operator's
control, and the request text itself is never stored on-chain.

## Compilation strategy

The Solidity source is compiled by a pinned `solc-js` compiler invoked through
`node contracts/compile.js`. There is no native `solc` to install, so the build
is identical on a laptop and in CI. The resulting artifact (ABI + bytecode) is
committed under `contracts/artifacts/`, which lets the runtime and the tests
deploy the contract to any endpoint without running a compiler.

## Extension points

- **Classifier.** The TF-IDF + logistic-regression model is a strong, explainable
  baseline. A transformer-based classifier could replace it behind the same
  `classify` interface, returning the same `ClassifiedRequest`.
- **Policy.** New rules (minimum-necessary checks, role-based limits, break-glass
  emergency access) slot into `policy.evaluate` without touching the chain.
- **Registry target.** Pointing `CC_CHAIN_RPC_URL` and `CC_CONTRACT_ADDRESS` at a
  live node is the only change needed to record consent on a real chain.
