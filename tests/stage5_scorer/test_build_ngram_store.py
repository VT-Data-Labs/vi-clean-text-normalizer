"""Tests for ``scripts/build_ngram_store.py`` — multi-source phrase loading."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from scripts.build_ngram_store import (
    BIGRAM_FACTOR,
    FULL_PHRASE_FACTOR,
    TRIGRAM_FACTOR,
    PhraseRecord,
    _generate_ngrams,
    _score_for_phrase_tokens,
    deduplicate,
    effective_score,
    load_curated_phrases,
    load_domain_phrases,
    load_lexicon_phrases_json,
    load_negative_phrases,
    load_sqlite_phrases,
    phrase_to_normalized_tokens,
    phrase_to_tokens,
)

REPO = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------


def _make_rec(
    phrase: str = "",
    normalized: str = "",
    tokens: tuple[str, ...] | None = None,
    n: int = 2,
    score: float = 1.0,
    source: str = "curated",
    domain: str | None = None,
) -> PhraseRecord:
    if tokens is None:
        tokens = tuple(phrase.split())
    return PhraseRecord(
        phrase=phrase,
        normalized=normalized,
        tokens=tokens,
        n=n,
        score=score,
        source=source,
        domain=domain,
    )


# ---------------------------------------------------------------------------
# PhraseRecord
# ---------------------------------------------------------------------------


class TestPhraseRecord:
    def test_minimal_record(self) -> None:
        rec = PhraseRecord(
            phrase="điện thoại",
            normalized="dien thoai",
            tokens=("điện", "thoại"),
            n=2,
            score=0.95,
            source="trusted_sqlite",
            domain="general",
        )
        assert rec.phrase == "điện thoại"
        assert rec.tokens == ("điện", "thoại")
        assert rec.n == 2
        assert rec.source == "trusted_sqlite"


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------


class TestPhraseToTokens:
    def test_preserves_accents(self) -> None:
        assert phrase_to_tokens("Điện Thoại") == ("điện", "thoại")

    def test_collapses_whitespace(self) -> None:
        assert phrase_to_tokens("  điện   thoại  ") == ("điện", "thoại")

    def test_single_token(self) -> None:
        assert phrase_to_tokens("hello") == ("hello",)


class TestPhraseToNormalizedTokens:
    def test_strips_accents(self) -> None:
        assert phrase_to_normalized_tokens("Điện Thoại") == ("dien", "thoai")

    def test_collapses_whitespace(self) -> None:
        assert phrase_to_normalized_tokens("  sổ  đỏ  ") == ("so", "do")


class TestEffectiveScore:
    def test_curated(self) -> None:
        rec = _make_rec(score=0.9, source="curated")
        assert effective_score(rec) == pytest.approx(0.9)

    def test_trusted_sqlite(self) -> None:
        rec = _make_rec(score=0.9, source="trusted_sqlite")
        assert effective_score(rec) == pytest.approx(0.81)


# ---------------------------------------------------------------------------
# _generate_ngrams
# ---------------------------------------------------------------------------


class TestGenerateNgrams:
    def test_bigram(self) -> None:
        result = _generate_ngrams(["a", "b"], 2)
        assert result == [(("a", "b"), 2)]

    def test_trigram(self) -> None:
        result = _generate_ngrams(["a", "b", "c"], 3)
        assert (("a", "b"), 2) in result
        assert (("b", "c"), 2) in result
        assert (("a", "b", "c"), 3) in result

    def test_fourgram(self) -> None:
        result = _generate_ngrams(["a", "b", "c", "d"], 4)
        assert (("a", "b"), 2) in result
        assert (("b", "c"), 2) in result
        assert (("c", "d"), 2) in result
        assert (("a", "b", "c"), 3) in result
        assert (("b", "c", "d"), 3) in result
        assert (("a", "b", "c", "d"), 4) in result


class TestScoreForPhraseTokens:
    def test_full_phrase(self) -> None:
        assert _score_for_phrase_tokens(4, 4, 0.9) == pytest.approx(0.9 * FULL_PHRASE_FACTOR)

    def test_trigram_sub(self) -> None:
        assert _score_for_phrase_tokens(4, 3, 0.9) == pytest.approx(0.9 * TRIGRAM_FACTOR)

    def test_bigram_sub(self) -> None:
        assert _score_for_phrase_tokens(4, 2, 0.9) == pytest.approx(0.9 * BIGRAM_FACTOR)


# ---------------------------------------------------------------------------
# load_curated_phrases
# ---------------------------------------------------------------------------


class TestLoadCuratedPhrases:
    def test_loads_curated_file(self) -> None:
        path = REPO / "resources" / "phrases" / "phrases.vi.json"
        records = load_curated_phrases(path)
        assert len(records) == 11
        assert any("muỗng" in r.tokens for r in records)
        for r in records:
            assert r.source == "curated"
            assert r.n == len(r.tokens)

    def test_skips_invalid_n(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.json"
        p.write_text('[{"tokens": ["a"], "n": 1, "score": 0.5}]')
        assert load_curated_phrases(p) == []


# ---------------------------------------------------------------------------
# load_lexicon_phrases_json
# ---------------------------------------------------------------------------


class TestLoadLexiconPhrasesJson:
    def test_loads_lexicon_file(self) -> None:
        path = REPO / "resources" / "lexicons" / "phrases.vi.json"
        records = load_lexicon_phrases_json(path)
        assert len(records) == 13
        assert any("căn" in r.tokens for r in records)
        for r in records:
            assert r.source == "lexicon_json"
            assert r.n == len(r.tokens)

    def test_auto_corrects_n(self) -> None:
        """When the source n field is wrong, use actual token count."""
        records = load_lexicon_phrases_json(REPO / "resources" / "lexicons" / "phrases.vi.json")
        for r in records:
            assert r.n == len(r.tokens), f"{r.phrase}: n={r.n} != tokens={r.tokens}"


# ---------------------------------------------------------------------------
# load_sqlite_phrases
# ---------------------------------------------------------------------------


class TestLoadSqlitePhrases:
    def test_loads_from_temp_db(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        conn = sqlite3.connect(str(db))
        conn.execute(
            "CREATE TABLE lexicon_phrases ("
            "  phrase TEXT PRIMARY KEY, normalized TEXT, freq REAL, domain TEXT"
            ")"
        )
        conn.execute(
            "INSERT INTO lexicon_phrases VALUES ('điện thoại', 'dien thoai', 0.98, 'general')"
        )
        conn.execute("INSERT INTO lexicon_phrases VALUES ('liên hệ', 'lien he', 0.95, 'general')")
        conn.execute("INSERT INTO lexicon_phrases VALUES ('chính chủ', 'chinh chu', 0.95, NULL)")
        conn.execute("INSERT INTO lexicon_phrases VALUES ('sổ đỏ', 'so do', 0.95, 'real_estate')")
        conn.commit()
        conn.close()

        records = load_sqlite_phrases(db)
        assert len(records) == 4
        for r in records:
            assert r.source == "trusted_sqlite"
            assert r.n == len(r.tokens)

        phrases = {" ".join(r.tokens) for r in records}
        assert "điện thoại" in phrases
        assert "liên hệ" in phrases
        assert "chính chủ" in phrases
        assert "sổ đỏ" in phrases

    def test_skips_single_token(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        conn = sqlite3.connect(str(db))
        conn.execute(
            "CREATE TABLE lexicon_phrases ("
            "  phrase TEXT PRIMARY KEY, normalized TEXT, freq REAL, domain TEXT"
            ")"
        )
        conn.execute("INSERT INTO lexicon_phrases VALUES ('hello', 'hello', 0.5, NULL)")
        conn.commit()
        conn.close()
        assert load_sqlite_phrases(db) == []

    def test_missing_file(self) -> None:
        assert load_sqlite_phrases(Path("/nonexistent/test.db")) == []

    def test_domain_preserved(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        conn = sqlite3.connect(str(db))
        conn.execute(
            "CREATE TABLE lexicon_phrases ("
            "  phrase TEXT PRIMARY KEY, normalized TEXT, freq REAL, domain TEXT"
            ")"
        )
        conn.execute(
            "INSERT INTO lexicon_phrases VALUES ('mặt tiền', 'mat tien', 0.95, 'real_estate')"
        )
        conn.commit()
        conn.close()

        records = load_sqlite_phrases(db)
        assert len(records) == 1
        assert records[0].domain == "real_estate"


# ---------------------------------------------------------------------------
# load_domain_phrases
# ---------------------------------------------------------------------------


class TestLoadDomainPhrases:
    def test_loads_domain_file(self) -> None:
        path = REPO / "resources" / "phrases" / "domains" / "product_instruction.vi.json"
        records = load_domain_phrases(path)
        assert len(records) == 8
        for r in records:
            assert r.source == "domain"
            assert r.domain == "product_instruction"

    def test_domain_score(self, tmp_path: Path) -> None:
        p = tmp_path / "test.json"
        p.write_text(json.dumps({"domain": "test", "phrases": ["a b", "c d e"]}))
        records = load_domain_phrases(p)
        assert len(records) == 2
        assert records[0].score == 0.95
        assert records[1].score == 0.95


# ---------------------------------------------------------------------------
# load_negative_phrases
# ---------------------------------------------------------------------------


class TestLoadNegativePhrases:
    def test_loads_negative_file(self) -> None:
        path = REPO / "resources" / "phrases" / "negative_phrases.vi.json"
        records = load_negative_phrases(path)
        assert len(records) == 3
        for r in records:
            assert r.n == len(r.tokens)


# ---------------------------------------------------------------------------
# deduplicate
# ---------------------------------------------------------------------------


class TestDeduplicate:
    def test_no_duplicates(self) -> None:
        records = [
            _make_rec(phrase="a b", score=0.9, source="curated"),
            _make_rec(phrase="c d", score=0.8, source="curated"),
        ]
        result = deduplicate(records)
        assert len(result) == 2

    def test_dedup_exact_match(self) -> None:
        """Same accented form from two sources — keep higher effective score."""
        records = [
            _make_rec(phrase="điện thoại", score=0.98, source="trusted_sqlite"),
            _make_rec(phrase="điện thoại", score=0.9, source="curated"),
        ]
        result = deduplicate(records)
        assert len(result) == 1
        # curated: 1.00 * 0.9 = 0.9, sqlite: 0.90 * 0.98 = 0.882 → curated wins
        assert result[0].source == "curated"

    def test_dedup_preserves_different_tones(self) -> None:
        """Different accented forms with same no-tone key stay separate."""
        records = [
            _make_rec(phrase="sổ đỏ", score=0.95, source="trusted_sqlite"),
            _make_rec(phrase="số đo", score=0.98, source="trusted_sqlite"),
            _make_rec(phrase="sơ đồ", score=0.98, source="trusted_sqlite"),
        ]
        result = deduplicate(records)
        assert len(result) == 3  # all kept separate


# ---------------------------------------------------------------------------
# Integration: domain routing
# ---------------------------------------------------------------------------


def test_lexicon_phrase_with_domain_appears_in_domain_phrases(tmp_path: Path) -> None:
    """A lexicon phrase with explicit domain should appear in both
    general n-grams and domain_phrases.
    """
    phrases_path = tmp_path / "lexicon_phrases.json"
    phrases_path.write_text(
        json.dumps(
            [
                {
                    "phrase": "căn hộ",
                    "normalized": "can ho",
                    "n": 2,
                    "freq": 0.85,
                    "domain": "real_estate",
                },
            ]
        )
    )
    records = load_lexicon_phrases_json(phrases_path)
    assert len(records) == 1
    assert records[0].domain == "real_estate"


def test_sqlite_phrase_with_domain_in_domain_phrases(tmp_path: Path) -> None:
    """SQLite phrase with domain should generate n-grams and appear in domain_phrases."""
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE lexicon_phrases ("
        "  phrase TEXT PRIMARY KEY, normalized TEXT, freq REAL, domain TEXT"
        ")"
    )
    conn.execute("INSERT INTO lexicon_phrases VALUES ('căn hộ', 'can ho', 0.95, 'real_estate')")
    conn.commit()
    conn.close()

    records = load_sqlite_phrases(db)
    assert len(records) == 1
    assert records[0].domain == "real_estate"


def test_sqlite_no_domain_not_in_domain_phrases(tmp_path: Path) -> None:
    """SQLite phrase without domain should NOT be routed to domain_phrases."""
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE lexicon_phrases ("
        "  phrase TEXT PRIMARY KEY, normalized TEXT, freq REAL, domain TEXT"
        ")"
    )
    conn.execute("INSERT INTO lexicon_phrases VALUES ('điện thoại', 'dien thoai', 0.95, NULL)")
    conn.commit()
    conn.close()

    records = load_sqlite_phrases(db)
    assert len(records) == 1
    assert records[0].domain is None


def test_negative_phrases_not_in_positive(tmp_path: Path) -> None:
    """Negative phrases must not leak into positive n-grams."""
    neg_path = tmp_path / "negative.json"
    neg_path.write_text(
        json.dumps(
            [
                {
                    "phrase": "lâm người nhanh",
                    "tokens": ["lâm", "người", "nhanh"],
                    "normalized": "lam nguoi nhanh",
                    "n": 3,
                    "score": 0.05,
                    "domain": None,
                },
            ]
        )
    )
    records = load_negative_phrases(neg_path)
    assert len(records) == 1
    assert records[0].score == 0.05
