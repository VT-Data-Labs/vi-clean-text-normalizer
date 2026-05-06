"""CLI for testing Vietnamese OCR corrections.

Usage:
  uv run corrector "SỐ MÙÔNG (GẠT NGANG)"
  uv run corrector --domain milk_instruction --json < input.txt
  uv run corrector --interactive
"""

import argparse
import json
import sys
from dataclasses import asdict
from typing import Any, cast

from vn_corrector.common.types import CorrectionResult
from vn_corrector.stage2_lexicon import LexiconStore, load_default_lexicon
from vn_corrector.stage2_lexicon.backends.json_store import load_json_resource


def _build_lexicon_parser(subparsers: Any) -> argparse.ArgumentParser:
    """Add the 'lexicon' subcommand parser."""
    lex_parser = subparsers.add_parser("lexicon", help="Lexicon inspection tools")
    lex_parser.add_argument(
        "--lexicon-mode",
        choices=["json", "sqlite", "hybrid"],
        default="json",
        help="Lexicon backend mode (default: json)",
    )
    lex_parser.add_argument(
        "--lexicon-db",
        default=None,
        help="Path to SQLite lexicon DB (for sqlite/hybrid modes)",
    )
    lex_sub = lex_parser.add_subparsers(dest="lex_subcommand", required=True)

    # lexicon info
    lex_sub.add_parser("info", help="Show lexicon statistics")

    # lexicon lookup
    lookup_parser = lex_sub.add_parser("lookup", help="Look up a word in the lexicon")
    lookup_parser.add_argument("word", help="Word to look up")

    # lexicon candidates
    cand_parser = lex_sub.add_parser(
        "candidates", help="Show syllable candidates for a no-tone key"
    )
    cand_parser.add_argument("no_tone_key", help="No-tone lookup key (e.g. muong)")

    # lexicon validate
    lex_sub.add_parser("validate", help="Validate all built-in lexicon resource files")

    return cast(argparse.ArgumentParser, lex_parser)


def _lexicon_info(store: LexiconStore) -> None:
    """Print lexicon statistics."""
    print("Lexicon Statistics")
    print("=" * 40)
    print(f"Syllables:          {store.get_syllable_entry_count()}")
    print(f"Words:              {store.get_word_count()}")
    print(f"Abbreviations:      {store.get_abbreviation_count()}")
    print(f"Phrases:            {store.get_phrase_count()}")
    print(f"OCR Confusions:     {store.get_ocr_confusion_count()}")
    print(f"Foreign Words:      {store.get_foreign_word_count()}")


def _lexicon_lookup(store: LexiconStore, word: str) -> None:
    """Look up a word and print surface + accentless matches."""
    surface = store.lookup(word)
    accentless = store.lookup_accentless(word)

    print(f"Lookup: {word!r}")
    print("=" * 40)
    if surface.found:
        print(f"Surface match ({len(surface.entries)} entries):")
        for e in surface.entries:
            kind = getattr(e, "kind", type(e).__name__)
            surface_text = getattr(e, "surface", getattr(e, "phrase", ""))
            print(f"  [{kind}] {surface_text}")
    else:
        print("No surface match.")
    if accentless.found:
        print(f"\nAccentless match ({len(accentless.entries)} entries):")
        for e in accentless.entries:
            kind = getattr(e, "kind", type(e).__name__)
            surface_text = getattr(e, "surface", getattr(e, "phrase", ""))
            conf = e.score.confidence if hasattr(e, "score") else "N/A"
            print(f"  [{kind}] {surface_text} (conf={conf})")
    else:
        print("\nNo accentless match.")


def _lexicon_candidates(store: LexiconStore, key: str) -> None:
    """Print syllable candidates for a no-tone key."""
    candidates = store.get_syllable_candidates(key)
    if candidates:
        print(f"Candidates for no-tone key: {key!r}")
        print("=" * 40)
        for c in sorted(candidates, key=lambda x: x.score.confidence, reverse=True):
            print(f"  {c.surface:20s}  conf={c.score.confidence:.3f}")
    else:
        print(f"No candidates found for {key!r}")


def _lexicon_validate() -> None:
    """Validate all built-in lexicon resource files."""
    from vn_corrector.common.validation import validate_lexicon_file

    resources: list[tuple[str, str]] = [
        ("syllables.vi.json", "syllable"),
        ("words.vi.json", "word"),
        ("units.vi.json", "unit"),
        ("abbreviations.vi.json", "abbreviation"),
        ("foreign_words.json", "foreign_words"),
        ("phrases.vi.json", "phrase"),
        ("ocr_confusions.vi.json", "ocr_confusion"),
    ]
    all_valid = True
    for filename, ltype in resources:
        data = load_json_resource(filename)
        result = validate_lexicon_file(data, ltype)
        status = "PASS" if result.valid else "FAIL"
        print(f"[{status}] {filename}")
        if not result.valid:
            all_valid = False
            for err in result.errors:
                print(f"       {err}")
    if all_valid:
        print("\nAll lexicon files valid.")
    else:
        print("\nSome lexicon files have errors.")


def _run_lexicon(args: argparse.Namespace) -> None:
    """Dispatch lexicon subcommands."""
    from pathlib import Path

    mode: str = getattr(args, "lexicon_mode", "json")
    db_path = Path(args.lexicon_db) if getattr(args, "lexicon_db", None) else None
    store = load_default_lexicon(mode, db_path=db_path)  # type: ignore[arg-type]

    if args.lex_subcommand == "info":
        _lexicon_info(store)
    elif args.lex_subcommand == "lookup":
        _lexicon_lookup(store, args.word)
    elif args.lex_subcommand == "candidates":
        _lexicon_candidates(store, args.no_tone_key)
    elif args.lex_subcommand == "validate":
        _lexicon_validate()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments, detecting subcommands automatically.

    Detects if the first argument matches a known subcommand (e.g. ``lexicon``)
    and builds the appropriate parser with or without subparsers.
    """
    raw = argv if argv is not None else sys.argv[1:]
    is_lexicon = bool(raw) and raw[0] == "lexicon"

    if is_lexicon:
        parser = argparse.ArgumentParser(
            description="Vietnamese OCR correction test CLI",
        )
        subparsers = parser.add_subparsers(dest="command", required=True)
        _build_lexicon_parser(subparsers)
        # Disable the default help so it doesn't interfere with subparsers.
        # We only add --help to the subparsers where needed via the parent.
        return parser.parse_args(raw)

    parser = argparse.ArgumentParser(
        description="Vietnamese OCR correction test CLI",
    )
    parser.add_argument("text", nargs="*", help="Input text to correct")
    parser.add_argument(
        "--domain",
        default=None,
        help="Domain context (e.g., milk_instruction)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output raw JSON instead of formatted text",
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Interactive mode — read one line at a time",
    )
    parser.add_argument(
        "--pipeline",
        choices=["stage0", "full"],
        default="stage0",
        help="Which pipeline stage to run (default: stage0 — input normalization only)",
    )
    return parser.parse_args(raw)


def correct_text(text: str, _domain: str | None = None) -> CorrectionResult:
    """Run correction on input text.

    Currently runs Stage 0 (input normalization) only.
    Will wire through the full pipeline once milestones M1-M6 are built.
    """
    normalized = text.strip()
    return CorrectionResult(
        original_text=text,
        corrected_text=normalized,
        confidence=1.0 if text == normalized else 0.0,
    )


def format_output(result: CorrectionResult) -> str:
    """Human-readable formatted output."""
    lines = [
        f"Original:  {result.original_text}",
        f"Corrected: {result.corrected_text}",
        f"Confidence: {result.confidence:.2%}",
    ]
    if result.changes:
        lines.append("Changes:")
        for c in result.changes:
            lines.append(f"  [{c.span.start}:{c.span.end}] {c.original!r} → {c.replacement!r}")
    if result.flags:
        lines.append("Flags:")
        for f in result.flags:
            lines.append(f"  {f.flag_type}: {f.span_text!r} — {f.reason}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint — parses args and dispatches to lexicon or correction.

    Args:
        argv: Override for ``sys.argv[1:]`` (used in tests).

    """
    args = parse_args(argv)

    if getattr(args, "command", None) == "lexicon":
        _run_lexicon(args)
        return

    if getattr(args, "interactive", False):
        print("Interactive mode. Enter text (Ctrl-D to exit):", file=sys.stderr)
        domain = getattr(args, "domain", None)
        for line in sys.stdin:
            line = line.rstrip("\n")
            if not line:
                continue
            result = correct_text(line, domain)
            if getattr(args, "output_json", False):
                print(json.dumps(asdict(result), ensure_ascii=False))
            else:
                print(format_output(result))
                print()
        return

    text = " ".join(getattr(args, "text", []) or []) or sys.stdin.read().strip()

    if not text:
        print("Error: no input text provided.", file=sys.stderr)
        sys.exit(1)

    result = correct_text(text, getattr(args, "domain", None))

    if getattr(args, "output_json", False):
        print(json.dumps(asdict(result), ensure_ascii=False))
    else:
        print(format_output(result))


if __name__ == "__main__":
    main()
