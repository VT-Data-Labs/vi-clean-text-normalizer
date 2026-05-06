#!/usr/bin/env python3
"""Build the JSON n-gram store from curated phrase datasets.

Reads ``resources/phrases/phrases.vi.json`` and
``resources/phrases/negative_phrases.vi.json``, validates that
``n == len(tokens)`` for each entry, generates all constituent
bigrams/trigrams/fourgrams, and writes a single merged file at
``resources/ngrams/ngram_store.vi.json``.

Usage::

    uv run python scripts/build_ngram_store.py
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, cast

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

PHRASES_FILE = REPO / "resources" / "phrases" / "phrases.vi.json"
NEGATIVE_FILE = REPO / "resources" / "phrases" / "negative_phrases.vi.json"
DOMAINS_DIR = REPO / "resources" / "phrases" / "domains"
OUTPUT = REPO / "resources" / "ngrams" / "ngram_store.vi.json"


def _load_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        print(f"  [SKIP] {path} not found", file=sys.stderr)
        return []
    with path.open(encoding="utf-8") as f:
        data: list[dict[str, Any]] = cast("list[dict[str, Any]]", json.load(f))
    print(f"  [LOAD] {path} ({len(data)} entries)", file=sys.stderr)
    return data


def _validate(entry: dict[str, Any]) -> bool:
    """Return True if *entry* has valid n == len(tokens)."""
    n = entry.get("n", 0)
    tokens = entry.get("tokens", [])
    if n != len(tokens):
        print(
            f"  [WARN] {entry.get('phrase', '?')}: n={n} != len(tokens)={len(tokens)}",
            file=sys.stderr,
        )
        return False
    if n < 2:
        print(
            f"  [WARN] {entry.get('phrase', '?')}: n={n} < 2, skipping",
            file=sys.stderr,
        )
        return False
    return True


def _generate_ngrams(tokens: list[str], n: int) -> list[tuple[tuple[str, ...], int]]:
    """Yield ``(ngram, ngram_length)`` pairs for a phrase."""
    results: list[tuple[tuple[str, ...], int]] = []
    for nlen in range(2, n + 1):
        for i in range(len(tokens) - nlen + 1):
            results.append((tuple(tokens[i : i + nlen]), nlen))
    return results


def build() -> None:
    """Build the ngram store from curated phrase files and write to output."""
    bigrams: dict[str, float] = {}
    trigrams: dict[str, float] = {}
    fourgrams: dict[str, float] = {}
    domain_phrases: dict[str, dict[str, float]] = defaultdict(dict)
    negative_phrases: dict[str, float] = {}

    # -- Positive phrases ---------------------------------------------------
    for entry in _load_json(PHRASES_FILE):
        if not _validate(entry):
            continue
        tokens: list[str] = entry["tokens"]
        n: int = entry["n"]
        score: float = entry["score"]
        domain: str | None = entry.get("domain")

        for ngram_tuple, nlen in _generate_ngrams(tokens, n):
            key = " ".join(ngram_tuple)
            if nlen == 2:
                current = bigrams.get(key, 0.0)
                bigrams[key] = max(current, score)
            elif nlen == 3:
                current = trigrams.get(key, 0.0)
                trigrams[key] = max(current, score)
            elif nlen == 4:
                current = fourgrams.get(key, 0.0)
                fourgrams[key] = max(current, score)

        full_key = " ".join(tokens)
        if domain:
            current = domain_phrases[domain].get(full_key, 0.0)
            domain_phrases[domain][full_key] = max(current, score)

    # -- Negative phrases ---------------------------------------------------
    for entry in _load_json(NEGATIVE_FILE):
        if not _validate(entry):
            continue
        key = " ".join(entry["tokens"])
        current = negative_phrases.get(key, 0.0)
        negative_phrases[key] = max(current, entry["score"])

    # -- Domain phrase files ------------------------------------------------
    domain_dir = DOMAINS_DIR
    if domain_dir.exists():
        for domain_file in sorted(domain_dir.glob("*.vi.json")):
            with domain_file.open(encoding="utf-8") as f:
                domain_data = json.load(f)
            domain_name: str = domain_data["domain"]
            for phrase_text in domain_data.get("phrases", []):
                base_score = domain_phrases.get(domain_name, {}).get(phrase_text, 0.85)
                if base_score == 0.0:
                    base_score = 0.85
                current = domain_phrases[domain_name].get(phrase_text, 0.0)
                domain_phrases[domain_name][phrase_text] = max(current, base_score)

    # -- Write output -------------------------------------------------------
    store = {
        "version": 1,
        "language": "vi",
        "bigrams": dict(sorted(bigrams.items())),
        "trigrams": dict(sorted(trigrams.items())),
        "fourgrams": dict(sorted(fourgrams.items())),
        "domain_phrases": {
            domain: dict(sorted(phrases.items()))
            for domain, phrases in sorted(domain_phrases.items())
        },
        "negative_phrases": dict(sorted(negative_phrases.items())),
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(store, f, indent=2, ensure_ascii=False)

    # -- Summary ------------------------------------------------------------
    print(file=sys.stderr)
    print(f"  bigrams:       {len(bigrams):>5}", file=sys.stderr)
    print(f"  trigrams:      {len(trigrams):>5}", file=sys.stderr)
    print(f"  fourgrams:     {len(fourgrams):>5}", file=sys.stderr)
    print(f"  domain groups: {len(domain_phrases):>5}", file=sys.stderr)
    print(f"  negatives:     {len(negative_phrases):>5}", file=sys.stderr)
    print(f"\n  Written: {OUTPUT}", file=sys.stderr)


if __name__ == "__main__":
    build()
