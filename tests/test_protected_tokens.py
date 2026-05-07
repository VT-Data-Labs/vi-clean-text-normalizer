"""Tests for the refactored Stage 3 — engine, matchers, registry, and roundtrip.

Architecture:
    Engine (conflict resolution, mask, restore) — pure logic, no hardcoded regex
    RegexMatcher — patterns from config
    LexiconMatcher — entries from external files
    Registry — YAML-driven matcher loading
    Full pipeline — protect() with loaded matchers
    Backward compat — old ``protected_tokens`` module still works
"""

from __future__ import annotations

import pathlib
import tempfile

import pytest
import yaml

from vn_corrector.common.enums import SpanType
from vn_corrector.common.spans import ProtectedDocument, ProtectedSpan
from vn_corrector.stage3_protect import Matcher, load_matchers, mask, protect, restore
from vn_corrector.stage3_protect.engine import make_placeholder, resolve_conflicts
from vn_corrector.stage3_protect.matchers.lexicon import LexiconMatcher
from vn_corrector.stage3_protect.matchers.regex import RegexMatcher
from vn_corrector.stage3_protect.registry import _create_matcher

# =========================================================================
# Helpers
# =========================================================================


def _span(
    start: int,
    end: int,
    stype: SpanType = SpanType.NUMBER,
    priority: int = 1,
    value: str = "",
) -> ProtectedSpan:
    return ProtectedSpan(
        type=stype,
        start=start,
        end=end,
        value=value or f"txt[{start}:{end}]",
        priority=priority,
        source="test",
    )


# =========================================================================
# Engine — conflict resolution
# =========================================================================


class TestConflictResolution:
    def test_higher_priority_wins(self):
        candidates = [
            _span(0, 3, SpanType.NUMBER, priority=3),
            _span(0, 5, SpanType.UNIT, priority=4),
        ]
        final = resolve_conflicts(candidates, 5)
        assert len(final) == 1
        assert final[0].priority == 4
        assert final[0].start == 0
        assert final[0].end == 5

    def test_longer_span_wins_same_priority(self):
        candidates = [
            _span(3, 6, SpanType.DATE, priority=3),
            _span(3, 10, SpanType.DATE, priority=3),
        ]
        final = resolve_conflicts(candidates, 10)
        assert len(final) == 1
        assert final[0].end - final[0].start == 7

    def test_earlier_span_wins_tie(self):
        candidates = [
            _span(5, 8, SpanType.NUMBER, priority=3),
            _span(3, 6, SpanType.NUMBER, priority=3),
        ]
        final = resolve_conflicts(candidates, 10)
        assert len(final) == 1
        assert final[0].start == 3

    def test_non_overlapping_all_selected(self):
        candidates = [_span(0, 3), _span(5, 8), _span(10, 13)]
        final = resolve_conflicts(candidates, 15)
        assert len(final) == 3

    def test_adjacent_not_conflicting(self):
        candidates = [_span(0, 3), _span(3, 6)]
        final = resolve_conflicts(candidates, 10)
        assert len(final) == 2

    def test_empty_candidates(self):
        assert resolve_conflicts([], 10) == []

    def test_out_of_bounds_span_skipped(self):
        candidates = [_span(-1, 3), _span(2, 8), _span(0, 3)]
        final = resolve_conflicts(candidates, 10)
        # ProtectedSpan(-1,3) skipped (start < 0). ProtectedSpan(0,3) selected.
        # ProtectedSpan(2,8) skipped (overlaps with occupied[2:3]).
        assert len(final) == 1
        assert final[0].start == 0


# =========================================================================
# Engine — mask / restore
# =========================================================================


class TestMaskRestore:
    def test_mask_single_span(self):
        spans = [_span(0, 3, SpanType.NUMBER, 3, "123")]
        masked, pmap = mask("123 abc", spans)
        assert "123" not in masked
        assert "abc" in masked
        assert "⟪" in masked
        assert pmap

    def test_restore_single_span(self):
        spans = [_span(0, 3, SpanType.NUMBER, 3, "123")]
        masked, pmap = mask("123 abc", spans)
        assert restore(masked, pmap) == "123 abc"

    def test_roundtrip_multiple_spans(self):
        text = "Liên hệ https://example.com hoặc test@email.com"
        matchers = [
            RegexMatcher(
                "url",
                7,
                SpanType.URL,
                [
                    r"https?://[^\s<>\"'(){}|\\^`\[\]]+",
                ],
            ),
            RegexMatcher(
                "email",
                7,
                SpanType.EMAIL,
                [
                    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                ],
            ),
        ]
        candidates: list[ProtectedSpan] = []
        for m in matchers:
            candidates.extend(m.find(text))
        final = resolve_conflicts(candidates, len(text))
        masked, pmap = mask(text, final)
        assert restore(masked, pmap) == text

    def test_roundtrip_no_spans(self):
        masked, pmap = mask("hello world", [])
        assert masked == "hello world"
        assert pmap == {}
        assert restore(masked, pmap) == "hello world"

    def test_placeholders_unique(self):
        spans = [
            _span(0, 2, SpanType.NUMBER, 3, "12"),
            _span(5, 7, SpanType.NUMBER, 3, "34"),
        ]
        _, pmap = mask("aa 12 bb 34 cc", spans)
        assert len(pmap) == 2
        keys = list(pmap.keys())
        assert keys[0] != keys[1]

    def test_same_type_uses_different_counters(self):
        spans = [
            _span(0, 1, SpanType.UNIT, 4, "1"),
            _span(5, 6, SpanType.UNIT, 4, "2"),
        ]
        _, pmap = mask("a 1 b 2", spans)
        assert len(pmap) == 2
        keys = list(pmap.keys())
        assert keys[0] != keys[1]

    def test_placeholder_format(self):
        ph = make_placeholder(SpanType.URL, 0)
        assert ph == "⟪URL_0⟫"
        assert make_placeholder(SpanType.NUMBER, 5) == "⟪NUMBER_5⟫"


# =========================================================================
# RegexMatcher
# =========================================================================


class TestRegexMatcher:
    def test_single_pattern(self):
        m = RegexMatcher("digits", 3, SpanType.NUMBER, [r"\d+"])
        spans = m.find("abc 123 xyz")
        assert len(spans) == 1
        assert spans[0].value == "123"
        assert spans[0].type == SpanType.NUMBER

    def test_multiple_patterns(self):
        m = RegexMatcher(
            "multi",
            5,
            SpanType.CODE,
            [
                r"\d+[']-[A-Za-z0-9]+",
                r"\b[A-Z]{2,4}\b",
            ],
        )
        spans = m.find("2'-FL and DHA")
        assert len(spans) == 2
        values = {s.value for s in spans}
        assert "2'-FL" in values
        assert "DHA" in values

    def test_multiple_matches(self):
        m = RegexMatcher("nums", 3, SpanType.NUMBER, [r"\d+"])
        spans = m.find("a1b22c333")
        assert len(spans) == 3

    def test_no_match(self):
        m = RegexMatcher("nums", 3, SpanType.NUMBER, [r"\d+"])
        assert m.find("abc") == []

    def test_empty_patterns(self):
        m = RegexMatcher("empty", 1, SpanType.NUMBER, [])
        assert m.find("123") == []

    def test_require_ascii_filters_non_ascii(self):
        m = RegexMatcher("code", 5, SpanType.CODE, [r"\b[A-Z]{2,4}\b"], require_ascii=True)
        spans = m.find("DHA SỐ")
        assert len(spans) == 1
        assert spans[0].value == "DHA"

    def test_require_ascii_false_includes_all(self):
        m = RegexMatcher("letters", 1, SpanType.CODE, [r"\b\w+\b"], require_ascii=False)
        spans = m.find("DHA SỐ")
        assert len(spans) >= 2

    def test_source_field(self):
        m = RegexMatcher("test", 1, SpanType.URL, [r"\S+"])
        spans = m.find("hello")
        assert spans[0].source == "regex:test"


# =========================================================================
# LexiconMatcher
# =========================================================================


class TestLexiconMatcher:
    def test_basic_match(self):
        lex = LexiconMatcher("chem", 5, SpanType.CODE, lexicon={"DHA", "ARA", "LNT"})
        spans = lex.find("Hàm lượng DHA và ARA")
        values = {s.value for s in spans}
        assert "DHA" in values
        assert "ARA" in values
        assert "LNT" not in values

    def test_case_sensitive_default(self):
        lex = LexiconMatcher("chem", 5, SpanType.CODE, lexicon={"DHA"}, case_sensitive=True)
        assert len(lex.find("dha")) == 0
        assert len(lex.find("DHA")) == 1

    def test_case_insensitive(self):
        lex = LexiconMatcher("chem", 5, SpanType.CODE, lexicon={"dha"}, case_sensitive=False)
        spans = lex.find("DHA")
        assert len(spans) == 1

    def test_empty_lexicon(self):
        lex = LexiconMatcher("empty", 1, SpanType.CODE, set())
        assert lex.find("anything") == []

    def test_no_match(self):
        lex = LexiconMatcher("chem", 5, SpanType.CODE, lexicon={"XYZ"})
        assert lex.find("hello world") == []

    def test_source_field(self):
        lex = LexiconMatcher("chem", 5, SpanType.CODE, lexicon={"ABC"})
        assert lex.find("ABC")[0].source == "lexicon:chem"

    def test_word_boundary_respected(self):
        """Pure-alpha entries should not match inside longer words."""
        lex = LexiconMatcher("chem", 5, SpanType.CODE, lexicon={"DHA"})
        # "DHAP" should not match "DHA"
        assert len(lex.find("DHAP")) == 0

    def test_special_chars_match(self):
        """Entries with non-word characters match literally."""
        lex = LexiconMatcher("chem", 5, SpanType.CODE, lexicon={"2'-FL"})
        spans = lex.find("Hàm lượng 2'-FL")
        assert len(spans) == 1
        assert spans[0].value == "2'-FL"

    def test_load_from_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("# comment line\nDHA\nARA\n\nLNT\n")
            f.flush()
            path = f.name

        try:
            entries = LexiconMatcher.load_from_file(path)
            assert entries == {"DHA", "ARA", "LNT"}
        finally:
            import os

            os.unlink(path)

    def test_longest_match_preferred(self):
        """With overlapping entries, longer alternation wins."""
        lex = LexiconMatcher("test", 5, SpanType.CODE, lexicon={"AB", "ABC"})
        spans = lex.find("ABC")
        assert len(spans) == 1
        assert spans[0].value == "ABC"  # longest match via alternation order


# =========================================================================
# Registry — _create_matcher
# =========================================================================


class TestRegistryCreateMatcher:
    def test_regex_matcher_from_config(self):
        config = {
            "name": "test_regex",
            "type": "regex",
            "span_type": "url",
            "priority": 7,
            "patterns": [r"https?://\S+"],
        }
        m = _create_matcher(config, pathlib.Path("."))
        assert m is not None
        assert m.name == "test_regex"
        assert m.priority == 7
        spans = m.find("http://x.com")
        assert len(spans) == 1
        assert spans[0].type == SpanType.URL

    def test_lexicon_matcher_from_config(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("ABC\nXYZ\n")
            f.flush()
            path = f.name

        try:
            config = {
                "name": "test_lex",
                "type": "lexicon",
                "span_type": "code",
                "priority": 5,
                "source": path,
                "case_sensitive": True,
            }
            m = _create_matcher(config, pathlib.Path("."))
            assert m is not None
            assert m.name == "test_lex"
            spans = m.find("hello ABC world")
            assert len(spans) == 1
            assert spans[0].value == "ABC"
        finally:
            import os

            os.unlink(path)

    def test_unknown_type_returns_none(self):
        config = {"name": "bad", "type": "unknown", "span_type": "url", "priority": 1}
        assert _create_matcher(config, pathlib.Path(".")) is None

    def test_missing_patterns_returns_none(self):
        config = {"name": "bad", "type": "regex", "span_type": "url", "priority": 1, "patterns": []}
        assert _create_matcher(config, pathlib.Path(".")) is None

    def test_invalid_span_type_returns_none(self):
        config = {
            "name": "bad",
            "type": "regex",
            "span_type": "invalid",
            "priority": 1,
            "patterns": [r"\d+"],
        }
        assert _create_matcher(config, pathlib.Path(".")) is None


class TestRegistryLoadMatchers:
    def test_load_from_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = {
                "name": "url_test",
                "type": "regex",
                "span_type": "url",
                "priority": 7,
                "patterns": [r"https?://\S+"],
            }
            with open(pathlib.Path(tmpdir) / "url.yaml", "w") as f:
                yaml.dump(cfg, f)

            matchers = load_matchers(tmpdir)
            assert len(matchers) == 1
            assert matchers[0].name == "url_test"
            assert matchers[0].priority == 7

    def test_load_sorts_by_priority_desc(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for name, prio in [("low", 1), ("high", 9), ("mid", 5)]:
                cfg = {
                    "name": name,
                    "type": "regex",
                    "span_type": "url",
                    "priority": prio,
                    "patterns": [r"\S+"],
                }
                with open(pathlib.Path(tmpdir) / f"{name}.yaml", "w") as f:
                    yaml.dump(cfg, f)

            matchers = load_matchers(tmpdir)
            priorities = [m.priority for m in matchers]
            assert priorities == sorted(priorities, reverse=True)

    def test_missing_directory_raises(self):
        try:
            load_matchers("/tmp/nonexistent_dir_xyzzy")
            raise AssertionError("Expected NotADirectoryError")
        except NotADirectoryError:
            pass


# =========================================================================
# Full pipeline — protect() with loaded matchers
# =========================================================================


class TestProtectPipeline:
    def test_roundtrip_plain_text(self):
        m = RegexMatcher("nop", 1, SpanType.NUMBER, [r"\d+"])
        doc = protect("Xin chào thế giới", [m])
        assert restore(doc.masked_text, doc.placeholder_map) == doc.original_text

    def test_url_protected(self):
        matchers = load_matchers(
            str(pathlib.Path(__file__).resolve().parent.parent / "resources" / "matchers")
        )
        doc = protect("Visit https://example.com", matchers)
        assert "https://example.com" not in doc.masked_text
        assert restore(doc.masked_text, doc.placeholder_map) == doc.original_text

    def test_email_protected(self):
        matchers = [
            RegexMatcher(
                "email", 7, SpanType.EMAIL, [r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"]
            ),
        ]
        doc = protect("Email: test@example.org", matchers)
        assert "test@example.org" not in doc.masked_text
        assert restore(doc.masked_text, doc.placeholder_map) == doc.original_text

    def test_mixed_text_roundtrip(self):
        matchers = [
            RegexMatcher("url", 7, SpanType.URL, [r"https?://\S+"]),
            RegexMatcher(
                "email", 7, SpanType.EMAIL, [r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"]
            ),
            RegexMatcher("phone", 6, SpanType.PHONE, [r"\d{10,11}"]),
            RegexMatcher("number", 3, SpanType.NUMBER, [r"\d+(?:[.,]\d+)*"]),
            RegexMatcher("unit", 4, SpanType.UNIT, [r"\d+\s*(?:ml|kg|°C)\b"]),
            LexiconMatcher("chem", 5, SpanType.CODE, lexicon={"DHA", "ARA"}),
        ]
        text = "Liên hệ support@company.com hoặc 0987654321. Giá 50.000₫ cho 120ml nước."
        doc = protect(text, matchers)
        assert restore(doc.masked_text, doc.placeholder_map) == text
        assert "support@company.com" not in doc.masked_text
        assert "0987654321" not in doc.masked_text

    def test_unit_beats_number(self):
        matchers = [
            RegexMatcher("unit", 4, SpanType.UNIT, [r"\d+\s*(?:ml|kg|°C)\b"]),
            RegexMatcher("num", 3, SpanType.NUMBER, [r"\d+(?:[.,]\d+)*"]),
        ]
        text = "Thêm 120ml nước"
        doc = protect(text, matchers)
        assert "120ml" not in doc.masked_text

    def test_debug_info_present(self):
        m = RegexMatcher("url", 7, SpanType.URL, [r"https?://\S+"])
        doc = protect("Hello https://example.com world", [m])
        assert "candidate_count" in doc.debug_info
        assert "final_span_count" in doc.debug_info

    def test_empty_string(self):
        m = RegexMatcher("nop", 1, SpanType.NUMBER, [r"\d+"])
        doc = protect("", [m])
        assert doc.masked_text == ""
        assert doc.spans == ()
        assert doc.placeholder_map == {}

    def test_only_punctuation(self):
        m = RegexMatcher("nop", 1, SpanType.NUMBER, [r"\d+"])
        doc = protect("!@#$%^&*()", [m])
        assert restore(doc.masked_text, doc.placeholder_map) == "!@#$%^&*()"

    def test_newlines_preserved(self):
        m = RegexMatcher("nop", 1, SpanType.NUMBER, [r"\d+"])
        doc = protect("hello\nworld\nfoo", [m])
        assert restore(doc.masked_text, doc.placeholder_map) == "hello\nworld\nfoo"


# =========================================================================
# Full roundtrip with loaded YAML configs (integration test)
# =========================================================================


class TestIntegrationRoundtrip:
    """Full pipeline using YAML-loaded matchers from the project config."""

    _cfg_dir = pathlib.Path(__file__).resolve().parent.parent / "resources" / "matchers"
    _loaded_matchers: list[Matcher] | None = None

    @classmethod
    def _get_matchers(cls) -> list[Matcher]:
        if cls._loaded_matchers is None:
            if not cls._cfg_dir.is_dir():
                raise RuntimeError(f"Matcher config directory not found: {cls._cfg_dir}")
            cls._loaded_matchers = load_matchers(str(cls._cfg_dir))
        return cls._loaded_matchers

    def test_roundtrip_long_text(self):
        matchers = self._get_matchers()
        text = "Sản phẩm: 2'-FL, DHA, ARA. Liều lượng: 120ml mỗi ngày. Nhiệt độ: 40°C."
        doc = protect(text, matchers)
        assert restore(doc.masked_text, doc.placeholder_map) == text

    def test_key_tokens_masked(self):
        matchers = self._get_matchers()
        text = "Sản phẩm: 2'-FL, DHA, ARA. Liều lượng: 120ml mỗi ngày. Giá: $25.99. Giảm 10%."
        doc = protect(text, matchers)
        for token in ("2'-FL", "DHA", "ARA", "120ml", "$25.99", "10%"):
            assert token not in doc.masked_text, f"{token!r} should be masked"

    def test_no_false_positive_on_vi_uppercase(self):
        matchers = self._get_matchers()
        text = "SỐ MÙÔNG (GẠT NGANG)"
        doc = protect(text, matchers)
        assert restore(doc.masked_text, doc.placeholder_map) == text

    def test_product_instruction_text(self):
        matchers = self._get_matchers()
        text = "SỐ MÙÔNG (GẠT NGANG) - 120ml\nRỐT NƯỚC VÀO"
        doc = protect(text, matchers)
        assert restore(doc.masked_text, doc.placeholder_map) == text
        assert "120ml" not in doc.masked_text


# =========================================================================
# ProtectedDocument type
# =========================================================================


class TestProtectedDocumentType:
    def test_dataclass_fields(self):
        doc = ProtectedDocument(
            original_text="hello",
            masked_text="world",
            spans=(),
            placeholder_map={},
        )
        assert doc.original_text == "hello"
        assert doc.masked_text == "world"
        assert doc.spans == ()
        assert doc.placeholder_map == {}
        assert doc.debug_info == {}

    def test_debug_info_default(self):
        m = RegexMatcher("test", 1, SpanType.NUMBER, [r"\d+"])
        doc = protect("test", [m])
        assert isinstance(doc.debug_info, dict)


# =========================================================================
# Backward compatibility with old protected_tokens module
# =========================================================================


class TestBackwardCompat:
    def test_import_protect(self):
        from vn_corrector.protected_tokens import protect as old_protect

        doc = old_protect("hello https://example.com world")
        assert "https://example.com" not in doc.masked_text
        assert restore(doc.masked_text, doc.placeholder_map) == doc.original_text

    def test_import_matcher_aliases(self):
        from vn_corrector.protected_tokens import (
            RegexMatcher,
            URLMatcher,
        )

        assert URLMatcher is RegexMatcher

    def test_import_constants(self):
        from vn_corrector.protected_tokens import MATCHERS, PH_LEFT, PH_RIGHT

        assert PH_LEFT == "⟪"
        assert PH_RIGHT == "⟫"
        assert len(MATCHERS) > 0

    def test_import_resolve_conflicts(self):
        from vn_corrector.protected_tokens import resolve_conflicts as rc

        assert rc([], 10) == []


class TestMatcherInterface:
    def test_matcher_is_abstract(self):
        import abc

        assert issubclass(Matcher, abc.ABC)
        # Cannot instantiate an abstract class directly
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            Matcher()  # type: ignore[abstract]
