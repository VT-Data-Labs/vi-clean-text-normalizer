"""Tests for the JSON-backed n-gram store."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vn_corrector.stage5_scorer.backends.json_ngram_store import JsonNgramStore


@pytest.fixture
def sample_store(tmp_path: Path) -> JsonNgramStore:
    d = tmp_path / "ngrams"
    d.mkdir()
    p = d / "ngram_store.json"
    data = {
        "version": 1,
        "language": "vi",
        "bigrams": {"số muỗng": 0.9, "muỗng gạt": 0.85, "gạt ngang": 0.8},
        "trigrams": {"số muỗng gạt": 0.9, "muỗng gạt ngang": 0.85},
        "fourgrams": {"số muỗng gạt ngang": 0.9},
        "domain_phrases": {
            "product_instruction": {
                "số muỗng gạt ngang": 0.9,
                "làm nguội nhanh": 0.85,
            },
        },
        "negative_phrases": {
            "lâm người nhanh": 0.05,
            "làm người nhanh": 0.1,
        },
    }
    p.write_text(json.dumps(data), encoding="utf-8")
    return JsonNgramStore(str(p))


class TestJsonNgramStore:
    def test_bigram_score_found(self, sample_store: JsonNgramStore) -> None:
        assert sample_store.bigram_score("số", "muỗng") == pytest.approx(0.9)

    def test_bigram_score_missing(self, sample_store: JsonNgramStore) -> None:
        assert sample_store.bigram_score("xyz", "abc") == pytest.approx(0.0)

    def test_trigram_score_found(self, sample_store: JsonNgramStore) -> None:
        assert sample_store.trigram_score("số", "muỗng", "gạt") == pytest.approx(0.9)

    def test_trigram_score_missing(self, sample_store: JsonNgramStore) -> None:
        assert sample_store.trigram_score("a", "b", "c") == pytest.approx(0.0)

    def test_fourgram_score_found(self, sample_store: JsonNgramStore) -> None:
        assert sample_store.fourgram_score("số", "muỗng", "gạt", "ngang") == pytest.approx(0.9)

    def test_phrase_score_bigram(self, sample_store: JsonNgramStore) -> None:
        assert sample_store.phrase_score(("số", "muỗng")) == pytest.approx(0.9)

    def test_phrase_score_trigram(self, sample_store: JsonNgramStore) -> None:
        assert sample_store.phrase_score(("số", "muỗng", "gạt")) == pytest.approx(0.9)

    def test_phrase_score_fourgram(self, sample_store: JsonNgramStore) -> None:
        assert sample_store.phrase_score(("số", "muỗng", "gạt", "ngang")) == pytest.approx(0.9)

    def test_phrase_score_single_token(self, sample_store: JsonNgramStore) -> None:
        assert sample_store.phrase_score(("số",)) == pytest.approx(0.0)

    def test_phrase_score_not_found(self, sample_store: JsonNgramStore) -> None:
        assert sample_store.phrase_score(("abc", "def")) == pytest.approx(0.0)

    def test_domain_phrase_score_found(self, sample_store: JsonNgramStore) -> None:
        assert sample_store.domain_phrase_score(
            "product_instruction",
            ("số", "muỗng", "gạt", "ngang"),
        ) == pytest.approx(0.9)

    def test_domain_phrase_score_missing_domain(self, sample_store: JsonNgramStore) -> None:
        assert sample_store.domain_phrase_score(
            "unknown_domain",
            ("số", "muỗng"),
        ) == pytest.approx(0.0)

    def test_domain_phrase_score_missing_phrase(self, sample_store: JsonNgramStore) -> None:
        assert sample_store.domain_phrase_score(
            "product_instruction",
            ("abc",),
        ) == pytest.approx(0.0)

    def test_negative_phrase_score_found(self, sample_store: JsonNgramStore) -> None:
        assert sample_store.negative_phrase_score(("lâm", "người", "nhanh")) == pytest.approx(0.05)

    def test_negative_phrase_score_missing(self, sample_store: JsonNgramStore) -> None:
        assert sample_store.negative_phrase_score(("abc",)) == pytest.approx(0.0)

    def test_load_missing_file(self) -> None:
        store = JsonNgramStore("/nonexistent/path.json")
        assert store.bigram_score("a", "b") == pytest.approx(0.0)
        assert store.phrase_score(("a",)) == pytest.approx(0.0)
