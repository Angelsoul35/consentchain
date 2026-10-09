"""Load a real, public medical-text dataset to benchmark the classifier pipeline.

ConsentChain's classifier reads free-text health language and maps it to a
category. To prove that pipeline generalises on genuine clinical wording — not
only on the project's own synthetic templates — this module loads a **real,
public** dataset whose task has the same shape.

**Dataset:** ``gretelai/symptom_to_diagnosis`` (Hugging Face). Each row is a
plain-language, patient-written symptom narrative (``input_text``) labelled with
a clinical diagnosis (``output_text``). There are 22 conditions, evenly
represented. Example::

    input_text : "I have a rash on my face that is getting worse. It is red,
                  inflamed, and has blisters that are bleeding clear pus."
    output_text: "impetigo"

**Why this matches the classifier's task.** ConsentChain's classifier turns a
free-text access request into a *data category* (and a purpose). This dataset is
the data-category problem taken to its real-world extreme: instead of one
``DIAGNOSES`` bit, it asks *which of 22 real clinical conditions* a genuine
health narrative describes. Every label is an instance of the project's
:data:`~consentchain.scopes.DataCategory.DIAGNOSES` category (see
:data:`PROJECT_CATEGORY`), so the benchmark stress-tests the exact pipeline that
assigns that category, on real patient language it never saw.

**How it is used.** We reuse the project's own feature pipeline and model
hyper-parameters (see :mod:`consentchain.real_benchmark`) and benchmark them on
the dataset's *own* 22 diagnosis labels — a single-label, multi-class task, the
same model family the classifier uses for the purpose head.

The rows are fetched once from the Hugging Face datasets-server (no auth needed)
and a **balanced** subset is vendored under ``datasets/`` as JSONL, so the
benchmark and the tests run offline and deterministically. Regenerate with::

    python -m consentchain.real_data
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .scopes import DataCategory

#: Hugging Face dataset id (owner/name).
DATASET_ID = "gretelai/symptom_to_diagnosis"

#: Public datasets-server rows endpoint (no authentication required).
ROWS_API = "https://datasets-server.huggingface.co/rows"

#: The dataset ships a ``train`` and a ``test`` split; we pool both and rebalance.
SPLITS = ("train", "test")

#: Rows per class in the vendored, balanced subset. The smallest class has 37
#: distinct narratives across the pooled splits, so 35 keeps the subset perfectly
#: balanced with a little headroom (35 x 22 = 770 rows, ~0.14 MB of JSONL).
PER_CLASS = 35

#: The datasets-server returns at most 100 rows per request.
_PAGE = 100

#: Every diagnosis label in this dataset is an instance of the ConsentChain
#: ``DIAGNOSES`` data category, so the benchmark exercises the classifier's
#: diagnoses-recognition pathway on 22 real conditions.
PROJECT_CATEGORY = DataCategory.DIAGNOSES

#: Where the balanced subset is vendored (repository ``datasets/`` directory).
VENDORED_PATH = Path(__file__).resolve().parent.parent / "datasets" / "symptom_diagnosis.jsonl"


class DatasetFetchError(RuntimeError):
    """Raised when the dataset cannot be fetched after retrying."""


def _http_get_json(url: str, *, timeout: float = 60.0, retries: int = 4) -> dict:
    """GET ``url`` and parse JSON, retrying transient failures with backoff.

    This is the single point that touches the network; tests monkeypatch it (or
    :func:`fetch_rows`) so the suite never makes a real request.
    """
    if not url.startswith("https://"):
        raise ValueError(f"refusing to fetch a non-HTTPS url: {url!r}")
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "consentchain-benchmark"})
            with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310 - https scheme enforced above
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as error:
            last_error = error
            if attempt < retries - 1:
                time.sleep(0.5 * (2**attempt))
    raise DatasetFetchError(f"could not fetch {url!r} after {retries} attempts: {last_error}")


def _rows_url(offset: int, length: int, *, split: str, dataset: str) -> str:
    query = urllib.parse.urlencode(
        {
            "dataset": dataset,
            "config": "default",
            "split": split,
            "offset": offset,
            "length": length,
        }
    )
    return f"{ROWS_API}?{query}"


def fetch_rows(
    offset: int, length: int, *, split: str = "train", dataset: str = DATASET_ID
) -> tuple[list[tuple[str, str]], int]:
    """Fetch one page of rows as ``(text, label)`` pairs plus the split's total.

    Thin wrapper over :func:`_http_get_json`; monkeypatchable in tests.
    """
    payload = _http_get_json(_rows_url(offset, length, split=split, dataset=dataset))
    pairs: list[tuple[str, str]] = []
    for item in payload.get("rows", []):
        row = item["row"]
        text = str(row["input_text"]).strip()
        label = str(row["output_text"]).strip().lower()
        if text and label:
            pairs.append((text, label))
    total = int(payload.get("num_rows_total", len(pairs)))
    return pairs, total


def fetch_split(split: str, *, dataset: str = DATASET_ID) -> list[tuple[str, str]]:
    """Page through an entire split, returning all ``(text, label)`` pairs."""
    pairs: list[tuple[str, str]] = []
    offset = 0
    while True:
        page, total = fetch_rows(offset, _PAGE, split=split, dataset=dataset)
        pairs.extend(page)
        offset += _PAGE
        if offset >= total or not page:
            break
    return pairs


def fetch_balanced_dataset(
    *, per_class: int = PER_CLASS, splits: tuple[str, ...] = SPLITS, dataset: str = DATASET_ID
) -> list[tuple[str, str]]:
    """Fetch, pool the splits, and deterministically balance to ``per_class`` rows.

    Selection is deterministic (rows are sorted within each class before the cap),
    so regenerating the vendored subset always yields the same rows regardless of
    fetch order. Raises if any class has fewer than ``per_class`` rows.
    """
    by_label: dict[str, list[str]] = {}
    for split in splits:
        for text, label in fetch_split(split, dataset=dataset):
            by_label.setdefault(label, []).append(text)

    balanced: list[tuple[str, str]] = []
    for label in sorted(by_label):
        texts = sorted(set(by_label[label]))
        if len(texts) < per_class:
            raise DatasetFetchError(
                f"class {label!r} has only {len(texts)} rows; need {per_class}"
            )
        balanced.extend((text, label) for text in texts[:per_class])
    balanced.sort(key=lambda pair: (pair[1], pair[0]))
    return balanced


def write_jsonl(rows: list[tuple[str, str]], path: Path = VENDORED_PATH) -> Path:
    """Write ``(text, label)`` pairs as one JSON object per line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for text, label in rows:
            handle.write(json.dumps({"text": text, "label": label}, ensure_ascii=False) + "\n")
    return path


def load_dataset(path: Path = VENDORED_PATH) -> tuple[list[str], list[str]]:
    """Load the vendored balanced subset as ``(texts, labels)``.

    This is what the benchmark and the tests use: it reads the committed JSONL and
    never touches the network.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"vendored dataset not found at {path}; regenerate it with "
            "`python -m consentchain.real_data`"
        )
    texts: list[str] = []
    labels: list[str] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            texts.append(record["text"])
            labels.append(record["label"])
    return texts, labels


def regenerate(path: Path = VENDORED_PATH) -> Path:
    """Fetch the dataset from Hugging Face and (re)write the vendored subset."""
    rows = fetch_balanced_dataset()
    written = write_jsonl(rows, path)
    labels = sorted({label for _, label in rows})
    print(f"Wrote {len(rows)} rows ({len(labels)} classes) to {written}")
    return written


if __name__ == "__main__":
    regenerate()
