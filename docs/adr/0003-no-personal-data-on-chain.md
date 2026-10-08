# ADR 0003: No personal or clinical data on-chain

## Status

Accepted.

## Context

The point of putting consent on a chain is to make its history tamper-evident
and auditable by all parties. But a chain is also, by design, permanent and
widely replicated. Anything written to it is effectively impossible to erase.
Health data and patient identities must never land in such a place — both for
privacy law (a permanent ledger cannot honour a deletion request) and for basic
safety.

We needed the auditability of a ledger **without** writing anything sensitive to
it.

## Decision

Write only non-identifying, structural data on-chain:

- patients and requesters are each a **`bytes32` id**, the keccak hash of a
  stable off-chain handle;
- data categories are **bit positions** in a mask;
- purposes are **small integer codes**;
- plus an expiry and a version.

The request text, the patient's name, the clinical values, and the mapping from
a real identity to a handle all stay **off-chain**, under the operator's control.

## Consequences

- **Privacy by design.** The chain records that *some id* consented to *some
  categories* for *some purpose* until *some time*. It never reveals who or what.
- **Auditability kept.** The consent timeline — every grant and revoke, with a
  version and a timestamp — is fully reconstructable from events, which is the
  property we wanted.
- **Right to be forgotten stays feasible.** Because identities live off-chain,
  deleting the handle-to-identity mapping severs the link; the chain keeps only
  opaque ids.
- **Trade-off.** The operator holds the mapping from ids to real people and must
  protect it. This is an explicit, well-understood responsibility, and it keeps
  the sensitive data in a place that *can* enforce deletion, which the chain
  cannot.
