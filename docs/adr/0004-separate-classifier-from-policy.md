# ADR 0004: Separate the classifier from the policy

## Status

Accepted.

## Context

There are two very different questions in an access decision:

1. **A language question:** what is this request actually asking for?
2. **A governance question:** given what it asks for, is it allowed right now?

It is tempting to fold both into one component — have the model read the request
*and* say yes or no. That couples a probabilistic model to a decision with legal
weight, hides the rules inside model behaviour, and makes the whole thing hard to
audit and to change.

## Decision

Keep the two strictly apart:

- **`classifier.py`** answers only the language question. It returns a purpose, a
  category mask, a confidence, and an explanation. It knows nothing about any
  particular patient's consent.
- **`policy.py`** answers only the governance question. It is a pure function of
  the classified request and the consent read from the registry. It owns the
  final **allow / deny / review** decision and the reasons.

Low classifier confidence is handled by the policy, which routes the request to a
human **review** instead of acting on an uncertain reading.

## Consequences

- **The rules are auditable.** The policy is deterministic and small; a reviewer
  can read exactly why any decision was made.
- **The model is replaceable.** A better classifier can be swapped in behind the
  same interface without touching the rules or the chain.
- **Uncertainty is explicit.** The system never turns a shaky classification into
  a silent allow or deny; it asks a human. The decision authority is the policy,
  not the model.
- **Testable in isolation.** The classifier is tested on held-out data for
  accuracy; the policy is tested on hand-built classified requests for every
  decision path (allow, deny, review, expiry, sensitive). Neither test needs the
  other component to be good to be meaningful.
- **Trade-off.** Two components and an interface between them are slightly more
  code than one. The clarity, auditability, and testability are worth it for a
  decision that governs sensitive data.
