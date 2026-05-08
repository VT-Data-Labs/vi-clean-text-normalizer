#!/usr/bin/env python3
"""Build a trusted Vietnamese word lexicon from external dictionary sources.

Usage
-----
    python scripts/build_trusted_words_vi.py \\
        --output data/lexicon/trusted_words.vi.jsonl

Sources
-------
- **UVD-1** (Hugging Face) — undertheseanlp/UVD-1 (72k words)
- **underthesea/dictionary** — merged from hongocduc + tudientv + wiktionary (78k)
- **Aspell** — wooorm/dictionaries Vietnamese (6.6k)

Note: Viet74K is identical to UVD-1 (100% overlap), so it is excluded to
avoid double-counting.

Confidence logic (after deduplication of confirmed-identical sources)
----------------
| Agreement                    | confidence |
|------------------------------|------------|
| All 3 sources                | 1.00       |
| 2 sources                    | 0.98       |
| Only underthesea_merged      | 0.95       |
| Only UVD-1                   | 0.90       |
| Only Aspell                  | 0.92       |
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vn_corrector.common.enums import LexiconKind
from vn_corrector.stage1_normalize import (
    normalize_text,
    strip_accents,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("build_trusted_words_vi")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STRONG_SOURCES = frozenset({"underthesea_merged"})
SOURCE_CONFIDENCE: dict[str, float] = {
    "uvd_1": 0.90,
    "underthesea_merged": 0.95,
    "aspell_vi": 0.92,
    "vietnamese_names": 0.80,
}

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# Allow Vietnamese chars, ASCII letters, spaces, hyphens, apostrophes, dots
_VI_CHARS = (
    r"a-zA-Z"
    r"àáảãạăằắẳẵặâầấẩẫậ"
    r"èéẻẽẹêềếểễệ"
    r"ìíỉĩị"
    r"òóỏõọôồốổỗộơờớởỡợ"
    r"ùúủũụưừứửữự"
    r"ỳýỷỹỵ"
    r"đ"
    r"ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬ"
    r"ÈÉẺẼẸÊỀẾỂỄỆ"
    r"ÌÍỈĨỊ"
    r"ÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢ"
    r"ÙÚỦŨỤƯỪỨỬỮỰ"
    r"ỲÝỶỸỴĐ"
)
_RE_SYMBOLS = re.compile(rf"[^{_VI_CHARS}\s\-'\.]")
_SYMBOL_RATIO_LIMIT = 0.3
_MAX_LENGTH = 60


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class RawWord:
    """A word parsed from a single source, before merging."""

    normalized: str
    surface: str
    no_tone: str
    source: str


@dataclass
class MergedEntry:
    """A merged word entry with provenance tracking."""

    normalized: str
    surface: str
    no_tone: str
    sources: set[str] = field(default_factory=set)

    @property
    def num_sources(self) -> int:
        return len(self.sources)

    @property
    def confidence(self) -> float:
        n = self.num_sources
        if n >= 3:
            return 1.00
        if n == 2:
            return 0.98
        src = next(iter(self.sources))
        return SOURCE_CONFIDENCE.get(src, 0.90)

    @property
    def kind(self) -> LexiconKind:
        """Derive kind from source and content."""
        if "vietnamese_names" in self.sources and len(self.sources) == 1:
            return LexiconKind.NAME
        return LexiconKind.PHRASE if " " in self.normalized else LexiconKind.WORD

    def to_entry_dict(self) -> dict[str, Any]:
        """Serialize to a dict matching LexiconEntry fields."""
        entry_kind = self.kind
        return {
            "entry_id": f"lex:{self.normalized}:{entry_kind.value}",
            "surface": self.surface,
            "normalized": self.normalized,
            "no_tone": self.no_tone,
            "kind": entry_kind.value,
            "score": {
                "confidence": self.confidence,
                "frequency": 0.0,
            },
            "provenance": {
                "source": "external-dictionary",
                "source_name": "+".join(sorted(self.sources)),
            },
            "tags": ["trusted"],
        }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def check_garbage(word: str) -> tuple[bool, str | None]:
    """Return (is_bad, reason)."""
    if not word or not word.strip():
        return True, "empty"
    if len(word) > _MAX_LENGTH:
        return True, f"length > {_MAX_LENGTH}"
    if _EMAIL_RE.search(word):
        return True, "contains email"
    if _URL_RE.search(word):
        return True, "contains URL"
    if _CONTROL_RE.search(word):
        return True, "contains control chars"
    # Symbol ratio
    if len(word) > 0:
        symbols_removed = len(_RE_SYMBOLS.sub("", word))
        ratio = (len(word) - symbols_removed) / len(word)
        if ratio > _SYMBOL_RATIO_LIMIT:
            return True, "too many symbols"
    # Reject entries with digits making up >50% of chars
    digit_count = sum(1 for c in word if c.isdigit())
    if len(word) > 0 and digit_count / len(word) > 0.5:
        return True, "too many digits"
    return False, None


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------


def _read_lines(path: Path) -> list[str]:
    """Read non-empty stripped lines from a text file."""
    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def load_uvd1(path: Path) -> list[RawWord]:
    """Load UVD-1 plain-text word list (one word per line)."""
    words: list[RawWord] = []
    for line in _read_lines(path):
        norm = normalize_text(line)
        bad, _ = check_garbage(norm)
        if bad:
            continue
        words.append(
            RawWord(normalized=norm, surface=line, no_tone=strip_accents(norm), source="uvd_1")
        )
    return words


def load_underthesea_merged(path: Path) -> list[RawWord]:
    """Load undertheseanlp merged JSONL (each line: {text, source})."""
    words: list[RawWord] = []
    for line in _read_lines(path):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        word = (entry.get("text") or "").strip()
        if not word:
            continue
        norm = normalize_text(word)
        bad, _ = check_garbage(norm)
        if bad:
            continue
        words.append(
            RawWord(
                normalized=norm,
                surface=word,
                no_tone=strip_accents(norm),
                source="underthesea_merged",
            )
        )
    return words


def load_aspell(path: Path) -> list[RawWord]:
    """Load Aspell dictionary (count line + word list)."""
    lines = _read_lines(path)
    if not lines:
        return []
    start = 1 if lines[0].isdigit() else 0
    words: list[RawWord] = []
    for line in lines[start:]:
        word = line.split("/")[0].strip()
        if not word:
            continue
        norm = normalize_text(word)
        bad, _ = check_garbage(norm)
        if bad:
            continue
        words.append(
            RawWord(normalized=norm, surface=word, no_tone=strip_accents(norm), source="aspell_vi")
        )
    return words


def load_names(path: Path, source_name: str = "vietnamese_names") -> list[RawWord]:
    """Load Vietnamese name lists (plain text, one name per line)."""
    words: list[RawWord] = []
    for line in _read_lines(path):
        # Skip non-Vietnamese lines (ASCII-only names are not useful)
        if not any(ord(c) > 127 for c in line):
            continue
        # Normalize and check if it looks like a Vietnamese name
        norm = normalize_text(line)
        bad, _ = check_garbage(norm)
        if bad:
            continue
        # Only accept entries with Vietnamese characters
        if any(ord(c) > 127 for c in norm):
            words.append(
                RawWord(
                    normalized=norm,
                    surface=line.strip(),
                    no_tone=strip_accents(norm),
                    source=source_name,
                )
            )
    return words


# ---------------------------------------------------------------------------
# Merge logic
# ---------------------------------------------------------------------------


def merge_words(all_words: list[RawWord]) -> list[MergedEntry]:
    """Merge raw words from multiple sources, deduplicating by normalized form.

    When a word appears in multiple sources, the surface from the highest-
    confidence source is kept.
    """
    grouped: dict[str, MergedEntry] = {}
    for rw in all_words:
        if rw.normalized not in grouped:
            grouped[rw.normalized] = MergedEntry(
                normalized=rw.normalized,
                surface=rw.surface,
                no_tone=rw.no_tone,
                sources=set(),
            )
        grouped[rw.normalized].sources.add(rw.source)
        # Prefer surface from highest-confidence source
        current_confidence = max(
            SOURCE_CONFIDENCE.get(s, 0.90) for s in grouped[rw.normalized].sources
        )
        candidate_confidence = SOURCE_CONFIDENCE.get(rw.source, 0.90)
        if candidate_confidence > current_confidence:
            grouped[rw.normalized].surface = rw.surface
    return list(grouped.values())


def build_no_tone_index(entries: list[MergedEntry]) -> dict[str, list[str]]:
    """Build NO_TONE → [surface, ...] index.

    Candidates are sorted by (confidence desc, num_sources desc, syllable_count asc).
    """
    index: dict[str, list[tuple[MergedEntry, int]]] = defaultdict(list)
    for e in entries:
        index[e.no_tone].append((e, len(e.normalized.split())))

    result: dict[str, list[str]] = {}
    for no_tone, candidates in index.items():
        candidates.sort(key=lambda x: (-x[0].confidence, -x[0].num_sources, x[1]))
        result[no_tone] = [c[0].surface for c in candidates]
    return result


# ---------------------------------------------------------------------------
# Exporters
# ---------------------------------------------------------------------------


def write_jsonl(entries: list[MergedEntry], path: Path) -> int:
    """Write entries as JSONL. Returns count."""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(path, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e.to_entry_dict(), ensure_ascii=False) + "\n")
            count += 1
    return count


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def build_trusted_lexicon(
    output: Path,
    data_dir: Path | None = None,
) -> list[MergedEntry]:
    """Run the full trusted lexicon build pipeline."""
    data_dir = data_dir or Path("data/raw")

    # Load all sources
    loaders: list[tuple[str, str, Any]] = [
        ("UVD-1", "uvd1.txt", load_uvd1),
        ("underthesea_merged", "underthesea_merged.txt", load_underthesea_merged),
        ("Aspell", "aspell_vi.dic", load_aspell),
        ("Vietnamese names (boy)", "boy.txt", lambda p: load_names(p, "vietnamese_names")),
        ("Vietnamese names (girl)", "girl.txt", lambda p: load_names(p, "vietnamese_names")),
    ]

    all_raw: list[RawWord] = []
    source_stats: list[tuple[str, int, int]] = []

    for name, filename, loader in loaders:
        filepath = data_dir / filename
        if not filepath.exists():
            log.warning("Source %s not found at %s, skipping", name, filepath)
            continue
        raw = loader(filepath)
        unique_norms = len({r.normalized for r in raw})
        all_raw.extend(raw)
        source_stats.append((name, len(raw), unique_norms))
        log.info("Loaded %6d words (%5d unique) from %s", len(raw), unique_norms, name)

    log.info("Total raw (pre-merge): %d", len(all_raw))

    # Merge
    merged = merge_words(all_raw)
    merged.sort(key=lambda e: e.normalized)

    # Confidence + kind distribution
    by_confidence: dict[str, int] = defaultdict(int)
    kind_counts: dict[str, int] = defaultdict(int)
    for e in merged:
        kind_counts[e.kind.value] += 1
        n = e.num_sources
        if n >= 3:
            by_confidence["1.00 (3+ sources)"] += 1
        elif n == 2:
            by_confidence["0.98 (2 sources)"] += 1
        else:
            src = next(iter(e.sources))
            label = f"{SOURCE_CONFIDENCE.get(src, 0.90):.2f} ({src})"
            by_confidence[label] += 1

    log.info("Merged to %d unique entries", len(merged))
    log.info("Kind distribution:")
    for kind_name in sorted(kind_counts.keys()):
        log.info("  %s: %d", kind_name, kind_counts[kind_name])
    log.info("Confidence distribution:")
    for label in sorted(by_confidence.keys(), reverse=True):
        log.info("  %s: %d", label, by_confidence[label])

    # Build NO_TONE index
    no_tone_index = build_no_tone_index(merged)
    total_candidates = sum(len(v) for v in no_tone_index.values())
    log.info("NO_TONE index: %d keys, %d total candidates", len(no_tone_index), total_candidates)

    # Sample
    for key in ["muong", "so", "rot", "lam", "dan", "nguoi"]:
        surfaces = no_tone_index.get(key, [])
        log.info("  %s → %s", key, surfaces[:6])

    # Write output
    jsonl_count = write_jsonl(merged, output)
    log.info("Wrote %d entries to %s", jsonl_count, output)

    log.info("Build complete — %d entries", len(merged))
    return merged


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Build trusted Vietnamese lexicon from external dictionaries",
    )
    parser.add_argument(
        "--output",
        default="data/lexicon/trusted_words.vi.jsonl",
        help="Output JSONL path",
    )
    parser.add_argument(
        "--data-dir",
        default="data/raw",
        help="Path to raw data directory",
    )
    return parser.parse_args(argv)


def main() -> None:
    """CLI entry point."""
    args = parse_args()
    log.info("Starting trusted lexicon build")
    entries = build_trusted_lexicon(
        output=Path(args.output),
        data_dir=Path(args.data_dir),
    )
    if not entries:
        log.error("Build produced no entries.")
        sys.exit(1)
    log.info("Done. Entries: %d", len(entries))


if __name__ == "__main__":
    main()
