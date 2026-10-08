# ADR 0002: An explainable linear classifier

## Status

Accepted.

## Context

The system has to turn a free-text access request into a structured claim: a
purpose and a set of data categories. Several model families could do this:

- a large language model prompted to extract the fields;
- a deep text classifier (a fine-tuned transformer);
- a classic linear model on bag-of-words / TF-IDF features.

A consent decision affects whether sensitive health data is released. If a
request is classified wrongly, the system either leaks data or blocks care. So
the model's output has to be **auditable**: a reviewer must be able to see *why*
a request was read the way it was. It also has to be deterministic and run with
no external service and no secrets.

## Decision

Use a **TF-IDF vectoriser** feeding **logistic regression**: a multi-class model
for the purpose and a one-vs-rest model for the categories (a multi-label
problem). For any prediction, read off the tokens that drove the purpose decision
by multiplying the request's TF-IDF vector by the model's coefficients.

## Consequences

- **Explainable by construction.** The decision is a weighted sum of word
  features, so the top contributing terms are the explanation — no post-hoc
  approximation needed.
- **Deterministic and offline.** The model trains from a fixed synthetic dataset,
  runs locally, and needs no API key or network.
- **Strong on the task.** On held-out data the purpose accuracy and the category
  micro-F1 are both very high, because the language of these requests is
  distinctive.
- **The model does not decide alone.** It outputs a confidence; the policy layer
  turns a low-confidence classification into a human **review** rather than a
  guess. The governance decision stays with the rules, not the model.
- **Trade-off.** A linear model on templated text is less robust to very
  different phrasing than a large pretrained model. The `classify` interface is
  designed so a stronger model can replace it later without changing the policy
  or the chain.
