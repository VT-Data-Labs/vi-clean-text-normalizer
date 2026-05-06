"""JSON-backed n-gram store implementation.

Loads a single ``ngram_store.vi.json`` file produced by the
``scripts/build_ngram_store.py`` build script.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vn_corrector.stage5_scorer.ngram_store import NgramStore


class JsonNgramStore(NgramStore):
    """N-gram store backed by a pre-built JSON file."""

    def __init__(self, path: str) -> None:
        self._bigrams: dict[str, float] = {}
        self._trigrams: dict[str, float] = {}
        self._fourgrams: dict[str, float] = {}
        self._domain_phrases: dict[str, dict[str, float]] = {}
        self._negative_phrases: dict[str, float] = {}

        if not Path(path).exists():
            return

        with open(path, encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)

        self._bigrams = {k: float(v) for k, v in data.get("bigrams", {}).items()}
        self._trigrams = {k: float(v) for k, v in data.get("trigrams", {}).items()}
        self._fourgrams = {k: float(v) for k, v in data.get("fourgrams", {}).items()}
        self._domain_phrases = {
            domain: {phrase: float(s) for phrase, s in phrases.items()}
            for domain, phrases in data.get("domain_phrases", {}).items()
        }
        self._negative_phrases = {k: float(v) for k, v in data.get("negative_phrases", {}).items()}

    # -- n-gram lookups -----------------------------------------------------

    def bigram_score(self, w1: str, w2: str) -> float:
        return self._bigrams.get(f"{w1} {w2}", 0.0)

    def trigram_score(self, w1: str, w2: str, w3: str) -> float:
        return self._trigrams.get(f"{w1} {w2} {w3}", 0.0)

    def fourgram_score(self, w1: str, w2: str, w3: str, w4: str) -> float:
        return self._fourgrams.get(f"{w1} {w2} {w3} {w4}", 0.0)

    def phrase_score(self, tokens: tuple[str, ...]) -> float:
        key = " ".join(tokens)
        if len(tokens) == 2:
            return self._bigrams.get(key, 0.0)
        if len(tokens) == 3:
            return self._trigrams.get(key, 0.0)
        if len(tokens) == 4:
            return self._fourgrams.get(key, 0.0)
        return 0.0

    # -- domain / negative lookups ------------------------------------------

    def domain_phrase_score(self, domain: str, tokens: tuple[str, ...]) -> float:
        domain_data = self._domain_phrases.get(domain)
        if domain_data is None:
            return 0.0
        return domain_data.get(" ".join(tokens), 0.0)

    def negative_phrase_score(self, tokens: tuple[str, ...]) -> float:
        return self._negative_phrases.get(" ".join(tokens), 0.0)
