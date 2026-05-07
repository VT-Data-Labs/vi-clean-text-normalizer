#!/usr/bin/env python3
"""Build the JSON n-gram store from all phrase sources.

Loads phrase records from:
  - resources/phrases/phrases.vi.json         (curated hand-authored phrases)
  - resources/lexicons/phrases.vi.json         (built-in lexicon phrases)
  - data/lexicon/trusted_lexicon.db            (SQLite trusted lexicon)
  - resources/phrases/domains/*.vi.json        (domain-specific phrase files)
  - resources/phrases/negative_phrases.vi.json (explicit negative penalties)

All sources are normalised into a common ``PhraseRecord``, deduplicated
by lower-cased accented token tuple (highest effective score wins),
then emitted as a single ``ngram_store.vi.json``.

Usage::

    uv run python scripts/build_ngram_store.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vn_corrector.stage1_normalize import strip_accents

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

CURATED_PHRASES_FILE = REPO / "resources" / "phrases" / "phrases.vi.json"
LEXICON_PHRASES_FILE = REPO / "resources" / "lexicons" / "phrases.vi.json"
TRUSTED_LEXICON_DB = REPO / "data" / "lexicon" / "trusted_lexicon.db"
NEGATIVE_FILE = REPO / "resources" / "phrases" / "negative_phrases.vi.json"
DOMAINS_DIR = REPO / "resources" / "phrases" / "domains"
OUTPUT_FILE = REPO / "data" / "processed" / "ngram_store.vi.json"

SOURCE_WEIGHTS: dict[str, float] = {
    "curated": 1.00,
    "domain": 0.95,
    "trusted_sqlite": 0.90,
    "lexicon_json": 0.85,
    "corpus_mined": 0.45,
}

DEFAULT_FREQ: dict[str, float] = {
    "curated": 1.00,
    "domain": 0.95,
    "trusted_sqlite": 0.90,
    "lexicon_json": 0.85,
    "corpus_mined": 0.45,
}

BIGRAM_FACTOR = 0.70
TRIGRAM_FACTOR = 0.85
FULL_PHRASE_FACTOR = 1.00


@dataclass(frozen=True)
class PhraseRecord:
    """Normalised phrase record from any source."""

    phrase: str
    normalized: str
    tokens: tuple[str, ...]
    n: int
    score: float
    source: str
    domain: str | None = None


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------


def phrase_to_tokens(phrase: str) -> tuple[str, ...]:
    """Split *phrase* into lowercased tokens preserving accents."""
    return tuple(phrase.strip().lower().split())


def phrase_to_normalized_tokens(phrase: str) -> tuple[str, ...]:
    """Split *phrase* into accent-stripped, lowercased tokens."""
    cleaned = " ".join(phrase.strip().split())
    return tuple(strip_accents(t) for t in cleaned.split())


def dedup_key(record: PhraseRecord) -> tuple[str, ...]:
    """Dedup key using lowercased accented tokens.

    Only phrases with the **same** accented form are merged,
    preserving distinct Vietnamese forms that share a no-tone key.
    """
    return tuple(t.lower() for t in record.tokens)


def effective_score(record: PhraseRecord) -> float:
    """Compute the source-weight-adjusted score for a record."""
    weight = SOURCE_WEIGHTS.get(record.source, 0.5)
    return weight * record.score


# ---------------------------------------------------------------------------
# Source adapters
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> list[dict[str, Any]]:
    """Load a JSON file, skipping if missing."""
    if not path.exists():
        print(f"  [SKIP] {path} not found", file=sys.stderr)
        return []
    with path.open(encoding="utf-8") as f:
        data: list[dict[str, Any]] = json.load(f)
    print(f"  [LOAD] {path} ({len(data)} entries)", file=sys.stderr)
    return data


def load_curated_phrases(path: Path) -> list[PhraseRecord]:
    """Load phrases from the hand-authored curated JSON file."""
    records: list[PhraseRecord] = []
    for entry in _load_json(path):
        tokens = tuple(entry["tokens"])
        n = entry["n"]
        if n < 2 or n != len(tokens):
            continue
        records.append(
            PhraseRecord(
                phrase=entry.get("phrase", ""),
                normalized=entry.get("normalized", ""),
                tokens=tokens,
                n=n,
                score=float(entry.get("score", DEFAULT_FREQ["curated"])),
                source="curated",
                domain=entry.get("domain"),
            )
        )
    return records


def load_lexicon_phrases_json(path: Path) -> list[PhraseRecord]:
    """Load phrases from the built-in lexicon JSON resource."""
    records: list[PhraseRecord] = []
    for entry in _load_json(path):
        phrase = entry["phrase"]
        tokens = phrase_to_tokens(phrase)
        # Use actual token count — the `n` field may be inaccurate
        n = len(tokens)
        if n < 2:
            continue
        records.append(
            PhraseRecord(
                phrase=phrase,
                normalized=entry.get("normalized", ""),
                tokens=tokens,
                n=n,
                score=float(entry.get("freq", DEFAULT_FREQ["lexicon_json"])),
                source="lexicon_json",
                domain=entry.get("domain"),
            )
        )
    return records


def load_sqlite_phrases(path: Path) -> list[PhraseRecord]:
    """Load phrases from the trusted SQLite lexicon database."""
    if not path.exists():
        print(f"  [SKIP] {path} not found", file=sys.stderr)
        return []
    records: list[PhraseRecord] = []
    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT phrase, normalized, freq, domain FROM lexicon_phrases")
        rows = cursor.fetchall()
        for row in rows:
            tokens = phrase_to_tokens(row["phrase"])
            n = len(tokens)
            if n < 2:
                continue
            records.append(
                PhraseRecord(
                    phrase=row["phrase"],
                    normalized=row["normalized"],
                    tokens=tokens,
                    n=n,
                    score=float(row["freq"]),
                    source="trusted_sqlite",
                    domain=row["domain"] if row["domain"] else None,
                )
            )
        conn.close()
        print(f"  [LOAD] {path} ({len(records)} entries)", file=sys.stderr)
    except sqlite3.Error as e:
        print(f"  [SKIP] SQLite error: {e}", file=sys.stderr)
    return records


def load_domain_phrases(path: Path) -> list[PhraseRecord]:
    """Load phrases from a domain-specific phrase JSON file."""
    records: list[PhraseRecord] = []
    with path.open(encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    domain: str = data["domain"]
    for phrase in data.get("phrases", []):
        records.append(
            PhraseRecord(
                phrase=phrase,
                normalized="",
                tokens=tuple(phrase.split()),
                n=len(phrase.split()),
                score=DEFAULT_FREQ["domain"],
                source="domain",
                domain=domain,
            )
        )
    return records


def load_negative_phrases(path: Path) -> list[PhraseRecord]:
    """Load negative (penalty) phrases from the negative JSON file."""
    records: list[PhraseRecord] = []
    for entry in _load_json(path):
        tokens = tuple(entry["tokens"])
        n = entry["n"]
        if n < 2 or n != len(tokens):
            continue
        records.append(
            PhraseRecord(
                phrase=entry.get("phrase", ""),
                normalized=entry.get("normalized", ""),
                tokens=tokens,
                n=n,
                score=float(entry.get("score", 0.05)),
                source="curated",
                domain=entry.get("domain"),
            )
        )
    return records


# ---------------------------------------------------------------------------
# Dedup + merge
# ---------------------------------------------------------------------------


def deduplicate(records: list[PhraseRecord]) -> list[PhraseRecord]:
    """Deduplicate records, keeping the highest effective score per dedup key."""
    seen: dict[tuple[str, ...], PhraseRecord] = {}
    for rec in records:
        key = dedup_key(rec)
        existing = seen.get(key)
        if existing is None:
            seen[key] = rec
        else:
            if effective_score(rec) > effective_score(existing):
                seen[key] = rec
    return list(seen.values())


# ---------------------------------------------------------------------------
# N-gram generation
# ---------------------------------------------------------------------------


def _generate_ngrams(tokens: list[str], n: int) -> list[tuple[tuple[str, ...], int]]:
    """Yield ``(ngram, ngram_length)`` pairs for a phrase."""
    results: list[tuple[tuple[str, ...], int]] = []
    for nlen in range(2, n + 1):
        for i in range(len(tokens) - nlen + 1):
            results.append((tuple(tokens[i : i + nlen]), nlen))
    return results


def _score_for_phrase_tokens(
    phrase_len: int,
    ngram_len: int,
    base_score: float,
) -> float:
    """Apply sliding-ngram discount: full phrase gets 100%, trigrams 85%, bigrams 70%."""
    if ngram_len == phrase_len:
        return base_score * FULL_PHRASE_FACTOR
    if ngram_len >= 3:
        return base_score * TRIGRAM_FACTOR
    return base_score * BIGRAM_FACTOR


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


def build() -> None:
    """Load all phrase sources, deduplicate, generate n-grams, write output."""
    print("Building n-gram store from all phrase sources...\n", file=sys.stderr)

    curated = load_curated_phrases(CURATED_PHRASES_FILE)
    lexicon_json = load_lexicon_phrases_json(LEXICON_PHRASES_FILE)
    trusted_sqlite = load_sqlite_phrases(TRUSTED_LEXICON_DB)

    domain_records: list[PhraseRecord] = []
    if DOMAINS_DIR.exists():
        for domain_file in sorted(DOMAINS_DIR.glob("*.vi.json")):
            domain_records.extend(load_domain_phrases(domain_file))

    negative_records = load_negative_phrases(NEGATIVE_FILE)

    source_counts = {
        "curated": len(curated),
        "domain": len(domain_records),
        "trusted_sqlite": len(trusted_sqlite),
        "lexicon_json": len(lexicon_json),
    }

    positive = deduplicate(curated + lexicon_json + trusted_sqlite + domain_records)
    raw = len(curated) + len(lexicon_json) + len(trusted_sqlite) + len(domain_records)
    print(f"\n  [DEDUP] {raw} raw -> {len(positive)} unique", file=sys.stderr)

    bigrams: dict[str, float] = {}
    trigrams: dict[str, float] = {}
    fourgrams: dict[str, float] = {}
    domain_phrases: dict[str, dict[str, float]] = defaultdict(dict)
    negative_phrases: dict[str, float] = {}

    for rec in positive:
        tokens = list(rec.tokens)
        n = rec.n
        base = rec.score

        for ngram_tuple, nlen in _generate_ngrams(tokens, n):
            key = " ".join(ngram_tuple)
            ngram_score = _score_for_phrase_tokens(n, nlen, base)
            ngram_score = min(max(ngram_score, 0.05), 1.0)

            if nlen == 2:
                current = bigrams.get(key, 0.0)
                bigrams[key] = max(current, ngram_score)
            elif nlen == 3:
                current = trigrams.get(key, 0.0)
                trigrams[key] = max(current, ngram_score)
            elif nlen == 4:
                current = fourgrams.get(key, 0.0)
                fourgrams[key] = max(current, ngram_score)

        full_key = " ".join(tokens)
        if rec.domain and rec.domain.strip():
            current = domain_phrases[rec.domain].get(full_key, 0.0)
            domain_phrases[rec.domain][full_key] = max(current, base)

    for rec in negative_records:
        key = " ".join(rec.tokens)
        current = negative_phrases.get(key, 0.0)
        negative_phrases[key] = max(current, rec.score)

    metadata = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source_counts": source_counts,
        "total_positive_ngrams": len(bigrams) + len(trigrams) + len(fourgrams),
        "total_negative_ngrams": len(negative_phrases),
    }

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
        "metadata": metadata,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(store, f, indent=2, ensure_ascii=False)

    print(file=sys.stderr)
    print(f"  bigrams:       {len(bigrams):>5}", file=sys.stderr)
    print(f"  trigrams:      {len(trigrams):>5}", file=sys.stderr)
    print(f"  fourgrams:     {len(fourgrams):>5}", file=sys.stderr)
    print(f"  domain groups: {len(domain_phrases):>5}", file=sys.stderr)
    print(f"  negatives:     {len(negative_phrases):>5}", file=sys.stderr)
    print(f"  metadata:      {metadata}", file=sys.stderr)
    print(f"\n  Written: {OUTPUT_FILE}", file=sys.stderr)


if __name__ == "__main__":
    build()
