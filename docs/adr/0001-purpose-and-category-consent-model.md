# ADR 0001: Purpose-scoped, category-exact consent

## Status

Accepted.

## Context

Consent in healthcare is not a single switch. A patient can agree to share some
kinds of data, with some requesters, for some purposes, for a limited time. A
system that models consent as one boolean ("may this clinic see my record?")
cannot express "my cardiologist may see my lab results for treatment, but no one
may use my genetic data for research." Collapsing those into one flag is how
data leaks.

We needed a consent model expressive enough to capture the real rules, but
simple enough to store and check cheaply on-chain.

## Decision

Model a consent record by the triple **(patient, requester, purpose)**, storing:

- a **category mask** — a 16-bit integer, one bit per data category;
- an **expiry** — Unix seconds;
- a **version** — bumped on every change.

Enforce three rules:

- **Purpose-scoped:** a different purpose is a different record. Treatment consent
  never authorises research.
- **Category-exact:** access is allowed only if `granted & requested == requested`.
- **Time-bound:** consent is valid only while `expiry > now`.

## Consequences

- **Expressive enough.** The model captures purpose, data category, requester,
  and time — the dimensions that matter for health consent.
- **Cheap to check.** Each rule is a single comparison. `hasConsent` is one
  mask-and and one timestamp check, which is trivial on-chain.
- **Easy to explain.** A denial can say exactly which categories are missing and
  whether the consent expired.
- **Trade-off.** A 16-bit mask caps the taxonomy at 16 categories. That is more
  than enough for this domain, and widening it later is a contract change, not a
  redesign.
- A purpose taxonomy (treatment, payment, operations, research) mirrors a model
  practitioners already understand, which makes the system easier to adopt.
