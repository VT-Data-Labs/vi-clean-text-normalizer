#!/usr/bin/env python3
"""Build the official SQLite runtime lexicon database.

Compiles JSON resource files and trusted-word JSONL into a single SQLite
database using the official ``SqliteLexiconStore`` schema.

Usage
-----
    python scripts/build_lexicon_db.py \\
        --resources resources/lexicons \\
        --trusted-jsonl data/lexicon/trusted_words.jsonl \\
        --output data/lexicon/trusted_lexicon.db

The output DB can be loaded at runtime with::

    from vn_corrector.stage2_lexicon import load_default_lexicon
    store = load_default_lexicon("sqlite", db_path="data/lexicon/trusted_lexicon.db")
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
from pathlib import Path

from vn_corrector.stage2_lexicon.backends.sqlite_store import _SCHEMA_SQL
from vn_corrector.stage2_lexicon.core.accent_stripper import strip_accents

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("build_lexicon_db")


# ---------------------------------------------------------------------------
# JSON → SQLite populators
# ---------------------------------------------------------------------------


def _populate_syllables(conn: sqlite3.Connection, resources_dir: Path) -> None:
    raw_path = resources_dir / "syllables.vi.json"
    data: list[dict[str, object]] = json.loads(raw_path.read_text(encoding="utf-8"))
    conn.executemany(
        "INSERT OR IGNORE INTO lexicon_syllables (base, surface, freq) VALUES (?, ?, ?)",
        _yield_syllable_rows(data),
    )


def _yield_syllable_rows(
    data: list[dict[str, object]],
) -> list[tuple[str, str, float]]:
    rows: list[tuple[str, str, float]] = []
    for entry in data:
        base = str(entry["base"])
        raw_forms = entry["forms"]
        forms: list[str] = [str(f) for f in raw_forms] if isinstance(raw_forms, list) else []
        freq_map: dict[str, float] = {}
        raw_freq = entry.get("freq")
        if isinstance(raw_freq, dict):
            freq_map = {str(k): float(v) for k, v in raw_freq.items()}
        for form in forms:
            rows.append((base, form, freq_map.get(form, 0.5)))
    return rows


def _populate_words(conn: sqlite3.Connection, resources_dir: Path) -> None:
    raw_path = resources_dir / "words.vi.json"
    data: list[dict[str, object]] = json.loads(raw_path.read_text(encoding="utf-8"))
    conn.executemany(
        "INSERT OR IGNORE INTO lexicon_words "
        "(surface, normalized, no_tone, kind, type, source, confidence, freq, domain, tags) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                str(entry["surface"]),
                str(entry.get("normalized", entry["surface"])),
                strip_accents(str(entry["surface"])),
                str(entry.get("kind", "word")),
                str(entry.get("type", "word")),
                "built-in",
                float(entry.get("freq", 1.0)),  # type: ignore[arg-type]
                float(entry.get("freq", 1.0)),  # type: ignore[arg-type]
                entry.get("domain"),
                json.dumps(entry.get("tags", []), ensure_ascii=False),
            )
            for entry in data
        ],
    )


def _populate_units(conn: sqlite3.Connection, resources_dir: Path) -> None:
    raw_path = resources_dir / "units.vi.json"
    data: list[dict[str, object]] = json.loads(raw_path.read_text(encoding="utf-8"))
    conn.executemany(
        "INSERT OR IGNORE INTO lexicon_units (surface, freq, domain) VALUES (?, ?, ?)",
        [
            (
                str(entry["surface"]),
                float(entry.get("freq", 1.0)),  # type: ignore[arg-type]
                str(entry.get("domain", "measurement")),
            )
            for entry in data
        ],
    )


def _populate_abbreviations(conn: sqlite3.Connection, resources_dir: Path) -> None:
    raw_path = resources_dir / "abbreviations.vi.json"
    data: list[dict[str, object]] = json.loads(raw_path.read_text(encoding="utf-8"))
    sql = (
        "INSERT OR IGNORE INTO lexicon_abbreviations "
        "(abbreviation, normalized, expansions, ambiguous, tags) VALUES (?, ?, ?, ?, ?)"
    )
    rows: list[tuple[str, str, str, int, str]] = []
    for entry in data:
        expansions = entry.get("expansions")
        expansions_json = (
            json.dumps(expansions, ensure_ascii=False) if isinstance(expansions, list) else "[]"
        )
        ambiguous = entry.get("ambiguous", isinstance(expansions, list) and len(expansions) > 1)
        rows.append(
            (
                str(entry["abbreviation"]),
                str(entry.get("normalized", str(entry["abbreviation"]).lower())),
                expansions_json,
                _to_int(ambiguous),
                json.dumps(entry.get("tags", []), ensure_ascii=False),
            )
        )
    conn.executemany(sql, rows)


def _populate_foreign_words(conn: sqlite3.Connection, resources_dir: Path) -> None:
    raw_path = resources_dir / "foreign_words.json"
    raw_data: list[dict[str, object]] | dict[str, object] = json.loads(
        raw_path.read_text(encoding="utf-8")
    )
    if isinstance(raw_data, list):
        words = [str(item) for item in raw_data]
        conn.executemany(
            "INSERT OR IGNORE INTO lexicon_foreign_words (word) VALUES (?)",
            [(w,) for w in words],
        )


def _populate_phrases(conn: sqlite3.Connection, resources_dir: Path) -> None:
    raw_path = resources_dir / "phrases.vi.json"
    data: list[dict[str, object]] = json.loads(raw_path.read_text(encoding="utf-8"))
    sql = (
        "INSERT OR IGNORE INTO lexicon_phrases "
        "(phrase, normalized, no_tone, n, freq, domain, tags) VALUES (?, ?, ?, ?, ?, ?, ?)"
    )
    conn.executemany(
        sql,
        [
            (
                str(entry["phrase"]),
                str(entry.get("normalized", entry["phrase"])),
                strip_accents(str(entry["phrase"])),
                int(entry["n"]),  # type: ignore[call-overload]
                float(entry.get("freq", 0.5)),  # type: ignore[arg-type]
                entry.get("domain"),
                json.dumps(entry.get("tags", []), ensure_ascii=False),
            )
            for entry in data
        ],
    )


def _populate_ocr_confusions(conn: sqlite3.Connection, resources_dir: Path) -> None:
    raw_path = resources_dir / "ocr_confusions.vi.json"
    data: list[dict[str, object]] = json.loads(raw_path.read_text(encoding="utf-8"))
    sql = (
        "INSERT OR IGNORE INTO lexicon_ocr_confusions "
        "(noisy, normalized_noisy, corrections, confidence) VALUES (?, ?, ?, ?)"
    )
    conn.executemany(
        sql,
        [
            (
                str(entry["noisy"]),
                strip_accents(str(entry["noisy"])),
                json.dumps(entry["corrections"], ensure_ascii=False),
                float(entry.get("confidence", 0.7)),  # type: ignore[arg-type]
            )
            for entry in data
        ],
    )


def _populate_from_json(conn: sqlite3.Connection, resources_dir: Path) -> None:
    """Populate all tables from JSON resource files in *resources_dir*."""
    _populate_syllables(conn, resources_dir)
    _populate_words(conn, resources_dir)
    _populate_units(conn, resources_dir)
    _populate_abbreviations(conn, resources_dir)
    _populate_foreign_words(conn, resources_dir)
    _populate_phrases(conn, resources_dir)
    _populate_ocr_confusions(conn, resources_dir)


def _to_int(value: object) -> int:
    if isinstance(value, bool):
        return 1 if value else 0
    return 1 if value else 0


# ---------------------------------------------------------------------------
# Trusted JSONL → SQLite populator
# ---------------------------------------------------------------------------


def _populate_trusted_jsonl(conn: sqlite3.Connection, jsonl_path: str | Path) -> int:
    """Load trusted word entries from a JSONL file into ``lexicon_words``.

    Each line is a serialized ``LexiconEntry`` dict.  Entries are inserted
    into ``lexicon_words`` with metadata columns populated from the
    JSONL fields.

    Entries whose ``kind`` is ``"phrase"`` are inserted into
    ``lexicon_phrases`` instead.
    """
    path = Path(jsonl_path)
    if not path.is_file():
        return 0

    word_rows: list[tuple[str, str, str, str, str, str, float, float, str | None, str]] = []
    phrase_rows: list[tuple[str, str, str, int, float, str | None, str]] = []
    count = 0

    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue

            surface = raw.get("surface", "")
            no_tone = raw.get("no_tone", "")
            if not surface or not no_tone:
                continue
            normalized = raw.get("normalized", "") or surface
            kind_str = raw.get("kind", "word")
            provenance = raw.get("provenance", {})
            source = provenance.get("source", "external-dictionary")
            tags_json = json.dumps(raw.get("tags", []), ensure_ascii=False)
            conf = float(raw.get("score", {}).get("confidence", 1.0))
            freq = float(raw.get("score", {}).get("frequency", 0.0))
            domain = raw.get("domain")

            if kind_str == "phrase":
                phrase_rows.append(
                    (
                        surface,
                        normalized,
                        no_tone,
                        len(surface.split()),
                        freq or conf,
                        domain,
                        tags_json,
                    )
                )
            else:
                word_rows.append(
                    (
                        surface,
                        normalized,
                        no_tone,
                        kind_str,
                        kind_str,
                        source,
                        conf,
                        freq,
                        domain,
                        tags_json,
                    )
                )
            count += 1

    if word_rows:
        conn.executemany(
            "INSERT OR REPLACE INTO lexicon_words "
            "(surface, normalized, no_tone, kind, type, source, confidence, freq, domain, tags) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            word_rows,
        )
    if phrase_rows:
        conn.executemany(
            "INSERT OR IGNORE INTO lexicon_phrases "
            "(phrase, normalized, no_tone, n, freq, domain, tags) VALUES (?, ?, ?, ?, ?, ?, ?)",
            phrase_rows,
        )

    return count


# ---------------------------------------------------------------------------
# Build metadata helpers
# ---------------------------------------------------------------------------


def _write_build_metadata(conn: sqlite3.Connection, metadata: dict[str, str]) -> None:
    """Write key-value metadata into ``lexicon_build_metadata``."""
    conn.executemany(
        "INSERT OR REPLACE INTO lexicon_build_metadata (key, value) VALUES (?, ?)",
        list(metadata.items()),
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _count_table(conn: sqlite3.Connection, table: str) -> int:
    """Return the row count for *table*."""
    row = conn.execute(f"SELECT COUNT(*) AS cnt FROM {table}").fetchone()
    return row[0] if row else 0


def build_lexicon_db(
    output: Path,
    resources_dir: Path,
    trusted_jsonl: Path | None = None,
) -> dict[str, int]:
    """Build the official SQLite runtime lexicon database.

    Returns a dict of table name → row count for the output DB.
    """
    output.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(output))
    conn.executescript(_SCHEMA_SQL)

    _populate_from_json(conn, resources_dir)

    trusted_count = 0
    if trusted_jsonl and trusted_jsonl.is_file():
        trusted_count = _populate_trusted_jsonl(conn, trusted_jsonl)
        log.info("Loaded %d trusted entries from %s", trusted_count, trusted_jsonl)
    else:
        log.info("No trusted JSONL file at %s, skipping", trusted_jsonl)

    conn.commit()

    counts = {
        "lexicon_syllables": _count_table(conn, "lexicon_syllables"),
        "lexicon_words": _count_table(conn, "lexicon_words"),
        "lexicon_units": _count_table(conn, "lexicon_units"),
        "lexicon_abbreviations": _count_table(conn, "lexicon_abbreviations"),
        "lexicon_foreign_words": _count_table(conn, "lexicon_foreign_words"),
        "lexicon_phrases": _count_table(conn, "lexicon_phrases"),
        "lexicon_ocr_confusions": _count_table(conn, "lexicon_ocr_confusions"),
        "trusted_entries_imported": trusted_count,
    }

    _write_build_metadata(
        conn,
        {
            "schema_version": "1.0",
            "build_timestamp": __import__("datetime").datetime.now().isoformat(),
            "resources_dir": str(resources_dir),
            "trusted_jsonl": str(trusted_jsonl) if trusted_jsonl else "",
            "syllable_count": str(counts["lexicon_syllables"]),
            "word_count": str(counts["lexicon_words"]),
            "unit_count": str(counts["lexicon_units"]),
            "abbreviation_count": str(counts["lexicon_abbreviations"]),
            "foreign_word_count": str(counts["lexicon_foreign_words"]),
            "phrase_count": str(counts["lexicon_phrases"]),
            "ocr_confusion_count": str(counts["lexicon_ocr_confusions"]),
            "trusted_imported": str(trusted_count),
        },
    )
    conn.commit()
    conn.close()

    log.info("Wrote %d syllables", counts["lexicon_syllables"])
    log.info("Wrote %d words", counts["lexicon_words"])
    log.info("Wrote %d units", counts["lexicon_units"])
    log.info("Wrote %d abbreviations", counts["lexicon_abbreviations"])
    log.info("Wrote %d foreign words", counts["lexicon_foreign_words"])
    log.info("Wrote %d phrases", counts["lexicon_phrases"])
    log.info("Wrote %d OCR confusions", counts["lexicon_ocr_confusions"])
    log.info("Imported %d trusted entries", trusted_count)
    log.info("Build complete — %s", output)

    return counts


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Build the official SQLite runtime lexicon database",
    )
    parser.add_argument(
        "--resources",
        default="resources/lexicons",
        help="Path to JSON resource directory (default: resources/lexicons)",
    )
    parser.add_argument(
        "--trusted-jsonl",
        default="data/lexicon/trusted_words.jsonl",
        help="Path to trusted-word JSONL (default: data/lexicon/trusted_words.jsonl)",
    )
    parser.add_argument(
        "--output",
        default="data/lexicon/trusted_lexicon.db",
        help="Output SQLite DB path (default: data/lexicon/trusted_lexicon.db)",
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    log.info("Starting lexicon DB build")
    build_lexicon_db(
        output=Path(args.output),
        resources_dir=Path(args.resources),
        trusted_jsonl=Path(args.trusted_jsonl),
    )


if __name__ == "__main__":
    main()
