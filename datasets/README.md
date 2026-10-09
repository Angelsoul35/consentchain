# Real benchmark data

This directory vendors a small, balanced subset of a **real, public** medical-text
dataset, used to benchmark the ConsentChain classifier pipeline on genuine
clinical language (not only the project's synthetic templates). See
[`consentchain/real_data.py`](../consentchain/real_data.py) for the loader and
[`consentchain/real_benchmark.py`](../consentchain/real_benchmark.py) for the
evaluation.

## Source

- **Dataset:** [`gretelai/symptom_to_diagnosis`](https://huggingface.co/datasets/gretelai/symptom_to_diagnosis)
- **Publisher:** Gretel AI
- **License:** Apache-2.0 (declared on the Hugging Face hub). Apache-2.0 permits
  redistribution of this balanced subset with attribution, which this file
  provides. See the dataset page for the authoritative terms.
- **Content:** 1065 English, plain-language, patient-written symptom narratives,
  each labelled with one of 22 clinical diagnoses (fine-grained, single-domain).
- **Fields:** `input_text` (the symptom narrative) and `output_text` (the
  diagnosis). We rename these to `text` and `label` in the vendored JSONL.

Example row:

```json
{"text": "I have a rash on my face that is getting worse. It is red, inflamed, and has blisters that are bleeding clear pus.", "label": "impetigo"}
```

## Why this dataset

ConsentChain's classifier reads free-text health language and maps it to a data
**category**. This dataset is that same problem taken to a real-world extreme:
instead of a single `diagnoses` bit, it asks *which of 22 real clinical
conditions* a genuine patient narrative describes. The benchmark reuses the
project's exact feature pipeline (the word + character `char_wb` TF-IDF
`FeatureUnion`) and the purpose head's logistic-regression hyper-parameters
(`C=2.0`, `max_iter=2000`) — the same linear, explainable model family the
classifier already runs — and evaluates it on the dataset's own labels.

## Label mapping

Every label in this dataset is an instance of the ConsentChain **`DIAGNOSES`**
data category (`consentchain.scopes.DataCategory.DIAGNOSES`). The benchmark
therefore stress-tests the classifier's diagnoses-recognition pathway on 22 real
conditions rather than templated phrasing. The 22 labels are:

```
allergy, arthritis, bronchial asthma, cervical spondylosis, chicken pox,
common cold, dengue, diabetes, drug reaction, fungal infection,
gastroesophageal reflux disease, hypertension, impetigo, jaundice, malaria,
migraine, peptic ulcer disease, pneumonia, psoriasis, typhoid,
urinary tract infection, varicose veins
```

None of these 22 conditions falls under the project's extra-sensitive categories
(`genetic`, `mental_health`), so the subset exercises the general-diagnosis
pathway; sensitive-category handling is covered by the policy-layer tests.

## The vendored subset

- **File:** `symptom_diagnosis.jsonl` — one JSON object per line (`text`,
  `label`).
- **Size:** 770 rows = **35 rows per class × 22 classes** (perfectly balanced),
  about 0.14 MB. 35 is used because the smallest class has 37 distinct narratives
  in the pooled train+test splits, so 35 keeps the subset balanced with headroom.
- **Selection:** the two upstream splits (`train`, `test`) are pooled,
  deduplicated, and the first 35 narratives per class (sorted) are taken. This is
  deterministic — regenerating always yields the same rows.

## How to regenerate

The loader fetches from the Hugging Face datasets-server (no authentication) and
rewrites the balanced subset:

```bash
python -m consentchain.real_data
```

This calls `consentchain.real_data.regenerate()`, which pages through the rows
API, balances the classes, and writes `symptom_diagnosis.jsonl`. The network
fetch uses `urllib` with retries and is monkeypatched in the test suite, so the
tests never touch the network.
