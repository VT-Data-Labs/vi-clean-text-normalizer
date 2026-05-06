"""Tests for the trusted Vietnamese lexicon build pipeline."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.build_trusted_lexicon import (
    MergedEntry,
    RawWord,
    build_no_tone_index,
    check_garbage,
    load_aspell,
    load_names,
    load_underthesea_merged,
    load_uvd1,
    merge_words,
    write_jsonl,
)
from vn_corrector.stage1_normalize import (
    normalize_text as normalize,
)
from vn_corrector.stage1_normalize import (
    strip_accents,
)

# ======================================================================
# Helpers
# ======================================================================


def _write_lines(path: Path, lines: list[str]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")


def _write_jsonl(path: Path, items: list[dict[str, object]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


# ======================================================================
# Tests: normalize / strip_accents / fix_lookalikes
# ======================================================================


class TestNormalize:
    def test_lowercase_nfc(self) -> None:
        assert normalize("MuỖNG") == "muỗng"

    def test_already_normalized(self) -> None:
        assert normalize("muỗng") == "muỗng"

    def test_empty_strip(self) -> None:
        assert normalize("  ") == ""

    def test_no_change_for_ascii(self) -> None:
        assert normalize("hello") == "hello"

    def test_fixes_eth_to_d(self) -> None:
        """U+00F0 (Icelandic eth) → đ (U+0111)."""
        assert normalize("anh ðào") == "anh đào"

    def test_fixes_capital_eth_to_d(self) -> None:
        """U+00D0 (Icelandic Eth capital) → Đ."""
        assert normalize("BÌNH ÐỊNH") == "bình định"

    def test_fixes_o_breve_to_o_horn(self) -> None:
        """U+014F (o with breve) → ơ (U+01A1)."""
        result = normalize("s\u014f")
        assert "\u014f" not in result, "O with breve should be replaced"

    def test_fixes_en_dash(self) -> None:
        assert normalize("abc–def") == "abc-def"

    def test_fixes_curly_quotes(self) -> None:
        assert normalize("o'clock") == "o'clock"
        assert normalize("o\u2019clock") == "o'clock"

    def test_fixes_curly_double_quotes(self) -> None:
        assert normalize("“hello”") == '"hello"'

    def test_fixes_d_hook_to_d(self) -> None:
        """U+0257 (d with hook) → đ."""
        # Direct test since \u0257 may not be visually distinct
        result = normalize("\u0257ường")
        assert result == "đường"


class TestStripAccents:
    def test_basic(self) -> None:
        assert strip_accents("muỗng") == "muong"

    def test_uppercase(self) -> None:
        assert strip_accents("SỐ MUỖNG") == "so muong"

    def test_all_tones(self) -> None:
        assert strip_accents("àáảãạăằắẳẵặ") == "a" * 11

    def test_eth_to_d_via_normalize(self) -> None:
        """Lookalike fixing is done by normalize_text, not strip_accents."""
        assert normalize("\u00f0ào") == "đào"
        assert strip_accents(normalize("\u00f0ào")) == "dao"

    def test_d_hook_to_d_via_normalize(self) -> None:
        """D with hook is fixed by normalize_text."""
        assert normalize("\u0257ường") == "đường"
        assert strip_accents(normalize("\u0257ường")) == "duong"

    def test_o_breve_to_o_via_normalize(self) -> None:
        """O with breve is fixed by normalize_text."""
        assert normalize("s\u014f") == "sơ"
        assert strip_accents(normalize("s\u014f")) == "so"

    def test_spanish_ntilde_preserved(self) -> None:
        """Spanish ñ (U+00F1) is not in our accent map, so it passes through."""
        result = strip_accents("jalapeño")
        # ñ is already lowercase and not in accent map, so it stays
        assert "ñ" in result

    def test_mixed_lookalikes_and_accents(self) -> None:
        """Real-world case: names with eth and tone marks."""
        strip_accents("BÌNH ÐỊNH")
        # normalize first converts Ð→Đ, then strip_accents strips to lowercase
        fixed = normalize("BÌNH ÐỊNH")
        assert fixed == "bình định"
        assert strip_accents(fixed) == "binh dinh"


# ======================================================================
# Tests: check_garbage
# ======================================================================


class TestCheckGarbage:
    def test_empty(self) -> None:
        assert check_garbage("") == (True, "empty")

    def test_whitespace_only(self) -> None:
        assert check_garbage("   ")[0] is True

    def test_too_long(self) -> None:
        assert check_garbage("x" * 61)[0] is True

    def test_valid_word(self) -> None:
        assert check_garbage("muỗng") == (False, None)

    def test_valid_phrase(self) -> None:
        assert check_garbage("số muỗng gạt ngang") == (False, None)

    def test_contains_email(self) -> None:
        assert check_garbage("test@example.com")[0] is True

    def test_contains_url(self) -> None:
        assert check_garbage("check https://example.com")[0] is True

    def test_too_many_symbols(self) -> None:
        assert check_garbage("#$%^&*()")[0] is True

    def test_control_chars(self) -> None:
        assert check_garbage("hello\x00world")[0] is True

    def test_hyphenated_word(self) -> None:
        """Hyphenated Vietnamese words are valid."""
        assert check_garbage("a-ba-giua") == (False, None)

    def test_apostrophe(self) -> None:
        assert check_garbage("o'clock") == (False, None)


# ======================================================================
# Tests: loaders
# ======================================================================


class TestLoadUVD1:
    def test_load_simple(self, tmp_path: Path) -> None:
        p = tmp_path / "uvd1.txt"
        _write_lines(p, ["muỗng", "mường", "   ", ""])
        words = load_uvd1(p)
        assert len(words) == 2
        assert words[0].normalized == "muỗng"
        assert words[0].source == "uvd_1"

    def test_empty_file(self, tmp_path: Path) -> None:
        p = tmp_path / "uvd1.txt"
        _write_lines(p, [])
        assert load_uvd1(p) == []

    def test_garbage_filtered(self, tmp_path: Path) -> None:
        p = tmp_path / "uvd1.txt"
        _write_lines(p, ["muỗng", "test@example.com", ""])
        words = load_uvd1(p)
        assert len(words) == 1


class TestLoadUnderthesea:
    def test_load_simple(self, tmp_path: Path) -> None:
        p = tmp_path / "ut.txt"
        _write_jsonl(
            p,
            [
                {"text": "muỗng", "source": ["hongocduc", "tudientv"]},
                {"text": "mường", "source": ["wiktionary"]},
            ],
        )
        words = load_underthesea_merged(p)
        assert len(words) == 2
        assert words[0].source == "underthesea_merged"

    def test_empty_file(self, tmp_path: Path) -> None:
        p = tmp_path / "ut.txt"
        _write_lines(p, [])
        assert load_underthesea_merged(p) == []

    def test_bad_json_skipped(self, tmp_path: Path) -> None:
        p = tmp_path / "ut.txt"
        _write_lines(p, ["not json", '{"text": "muỗng"}'])
        words = load_underthesea_merged(p)
        assert len(words) == 1


class TestLoadAspell:
    def test_load_with_count_line(self, tmp_path: Path) -> None:
        p = tmp_path / "aspell.dic"
        _write_lines(p, ["2", "muỗng", "muông"])
        words = load_aspell(p)
        assert len(words) == 2
        assert words[0].source == "aspell_vi"

    def test_load_without_count(self, tmp_path: Path) -> None:
        p = tmp_path / "aspell.dic"
        _write_lines(p, ["muỗng", "muông"])
        words = load_aspell(p)
        assert len(words) == 2

    def test_empty_file(self, tmp_path: Path) -> None:
        p = tmp_path / "aspell.dic"
        _write_lines(p, [])
        assert load_aspell(p) == []


class TestLoadNames:
    def test_load_simple(self, tmp_path: Path) -> None:
        p = tmp_path / "names.txt"
        _write_lines(p, ["An Hằng", "An Cơ", "Phương Chi"])
        words = load_names(p)
        assert len(words) == 3
        assert words[0].source == "vietnamese_names"
        assert words[0].normalized == "an hằng"

    def test_ascii_only_skipped(self, tmp_path: Path) -> None:
        p = tmp_path / "names.txt"
        _write_lines(p, ["John", "Maria", "An Hằng"])
        words = load_names(p)
        assert len(words) == 1
        assert words[0].normalized == "an hằng"

    def test_garbage_filtered(self, tmp_path: Path) -> None:
        p = tmp_path / "names.txt"
        _write_lines(p, ["An Hằng", "test@example.com", "a" * 70])
        words = load_names(p)
        assert len(words) == 1
        assert words[0].normalized == "an hằng"

    def test_no_vietnamese(self, tmp_path: Path) -> None:
        p = tmp_path / "names.txt"
        _write_lines(p, ["abc", "def"])
        assert load_names(p) == []


# ======================================================================
# Tests: merge_words
# ======================================================================


class TestMergeWords:
    def test_single_source(self) -> None:
        words = [
            RawWord(normalized="muỗng", surface="muỗng", no_tone="muong", source="uvd_1"),
        ]
        merged = merge_words(words)
        assert len(merged) == 1
        assert merged[0].confidence == 0.90

    def test_two_sources(self) -> None:
        words = [
            RawWord(normalized="muỗng", surface="muỗng", no_tone="muong", source="uvd_1"),
            RawWord(
                normalized="muỗng",
                surface="muỗng",
                no_tone="muong",
                source="underthesea_merged",
            ),
        ]
        merged = merge_words(words)
        assert len(merged) == 1
        assert merged[0].num_sources == 2
        assert merged[0].confidence == 0.98

    def test_three_sources(self) -> None:
        words = [
            RawWord(normalized="muỗng", surface="muỗng", no_tone="muong", source="uvd_1"),
            RawWord(
                normalized="muỗng",
                surface="muỗng",
                no_tone="muong",
                source="underthesea_merged",
            ),
            RawWord(normalized="muỗng", surface="muỗng", no_tone="muong", source="aspell_vi"),
        ]
        merged = merge_words(words)
        assert len(merged) == 1
        assert merged[0].num_sources == 3
        assert merged[0].confidence == 1.0

    def test_keeps_highest_confidence_surface(self) -> None:
        words = [
            RawWord(normalized="muỗng", surface="muỗng", no_tone="muong", source="uvd_1"),
            RawWord(
                normalized="muỗng",
                surface="MUỖNG",
                no_tone="muong",
                source="underthesea_merged",
            ),
        ]
        merged = merge_words(words)
        # underthesea has higher confidence (0.95 vs 0.90), so its surface wins
        assert merged[0].surface == "muỗng"

    def test_different_words_stay_separate(self) -> None:
        words = [
            RawWord(normalized="muỗng", surface="muỗng", no_tone="muong", source="uvd_1"),
            RawWord(normalized="mường", surface="mường", no_tone="muong", source="uvd_1"),
        ]
        merged = merge_words(words)
        assert len(merged) == 2


# ======================================================================
# Tests: NO_TONE index
# ======================================================================


class TestBuildNoToneIndex:
    def test_single_entry(self) -> None:
        entries = [
            MergedEntry(normalized="muỗng", surface="muỗng", no_tone="muong", sources={"uvd_1"}),
        ]
        index = build_no_tone_index(entries)
        assert "muong" in index
        assert index["muong"] == ["muỗng"]

    def test_multiple_candidates_sorted(self) -> None:
        entries = [
            MergedEntry(
                normalized="muỗng",
                surface="muỗng",
                no_tone="muong",
                sources={"uvd_1"},
            ),
            MergedEntry(
                normalized="mường",
                surface="mường",
                no_tone="muong",
                sources={"aspell_vi"},
            ),
        ]
        index = build_no_tone_index(entries)
        # aspell_vi (0.92) > uvd_1 (0.90)
        assert index["muong"][0] == "mường"
        assert index["muong"][1] == "muỗng"

    def test_confidence_sorting(self) -> None:
        entries = [
            MergedEntry(
                normalized="muỗng",
                surface="muỗng",
                no_tone="muong",
                sources={"uvd_1", "underthesea_merged"},
            ),
            MergedEntry(
                normalized="mường",
                surface="mường",
                no_tone="muong",
                sources={"uvd_1"},
            ),
        ]
        index = build_no_tone_index(entries)
        # muỗng (0.98, 2 sources) should come first
        assert index["muong"] == ["muỗng", "mường"]

    def test_empty_entries(self) -> None:
        assert build_no_tone_index([]) == {}


# ======================================================================
# Tests: serialization
# ======================================================================


class TestToEntryDict:
    def test_word_entry(self) -> None:
        e = MergedEntry(normalized="muỗng", surface="muỗng", no_tone="muong", sources={"uvd_1"})
        d = e.to_entry_dict()
        assert d["entry_id"] == "lex:muỗng:word"
        assert d["kind"] == "word"
        assert d["score"]["confidence"] == 0.90
        assert "trusted" in d["tags"]

    def test_phrase_entry(self) -> None:
        e = MergedEntry(
            normalized="số muỗng",
            surface="số muỗng",
            no_tone="so muong",
            sources={"uvd_1"},
        )
        d = e.to_entry_dict()
        assert d["kind"] == "phrase"

    def test_name_entry(self) -> None:
        e = MergedEntry(
            normalized="an hằng",
            surface="An Hằng",
            no_tone="an hang",
            sources={"vietnamese_names"},
        )
        d = e.to_entry_dict()
        assert d["entry_id"] == "lex:an hằng:name"
        assert d["kind"] == "name"
        assert d["score"]["confidence"] == 0.80


class TestWriteJsonl:
    def test_writes_one_per_line(self, tmp_path: Path) -> None:
        p = tmp_path / "out.jsonl"
        entries = [
            MergedEntry(normalized="a", surface="a", no_tone="a", sources={"uvd_1"}),
            MergedEntry(normalized="b", surface="b", no_tone="b", sources={"uvd_1"}),
        ]
        count = write_jsonl(entries, p)
        assert count == 2
        lines = p.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2


# ======================================================================
# Integration test
# ======================================================================


class TestBuildPipelineIntegration:
    """End-to-end test using temporary files."""

    def test_full_pipeline(self, tmp_path: Path) -> None:
        """Simulate the build pipeline with small test data."""
        # Create small source files
        uvd = tmp_path / "uvd1.txt"
        _write_lines(uvd, ["muỗng", "mường", "số muỗng"])

        uts = tmp_path / "underthesea_merged.txt"
        _write_jsonl(
            uts,
            [
                {"text": "muỗng", "source": ["hongocduc"]},
                {"text": "mường", "source": ["tudientv"]},
                {"text": "số muỗng", "source": ["wiktionary"]},
            ],
        )

        aspell = tmp_path / "aspell_vi.dic"
        _write_lines(aspell, ["4", "muỗng", "muông", "muống", "mương"])

        out_jsonl = tmp_path / "out.jsonl"

        # Run pipeline via imports
        from scripts.build_trusted_lexicon import build_trusted_lexicon

        entries = build_trusted_lexicon(
            output=out_jsonl,
            data_dir=tmp_path,
        )

        # Verify results
        assert len(entries) >= 4  # muỗng, mường, số muỗng, muông, muống, mương...

        # Check no_tone index works
        index = build_no_tone_index(entries)
        assert "muong" in index
        assert "muỗng" in index["muong"]

        # Check JSONL
        with open(out_jsonl) as f:
            lines = [json.loads(line) for line in f]
        assert len(lines) >= 4

    def test_garbage_filtered_integration(self, tmp_path: Path) -> None:
        """Garbage entries should not appear in output."""
        uvd = tmp_path / "uvd1.txt"
        _write_lines(uvd, ["muỗng", "", "   ", "test@example.com", "a" * 70])

        uts = tmp_path / "underthesea_merged.txt"
        _write_jsonl(uts, [{"text": "muỗng", "source": ["hongocduc"]}])

        aspell = tmp_path / "aspell_vi.dic"
        _write_lines(aspell, ["1", "muỗng"])

        out_jsonl = tmp_path / "out.jsonl"

        from scripts.build_trusted_lexicon import build_trusted_lexicon

        entries = build_trusted_lexicon(output=out_jsonl, data_dir=tmp_path)
        assert len(entries) == 1  # only muỗng survived
