"""
CLI for testing Vietnamese OCR corrections.

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
from vn_corrector.lexicon.store import LexiconStore


def _build_lexicon_parser(subparsers: Any) -> argparse.ArgumentParser:
    """Add the 'lexicon' subcommand parser."""
    lex_parser = subparsers.add_parser("lexicon", help="Lexicon inspection tools")
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


def _run_lexicon(args: argparse.Namespace) -> None:
    """Dispatch lexicon subcommands."""
    store = LexiconStore.load_default()

    if args.lex_subcommand == "info":
        print("Lexicon Statistics")
        print("=" * 40)
        syllable_count = sum(len(v) for v in store._syllable_index.values())
        phrase_count = sum(len(v) for v in store._phrase_index.values())
        print(f"Syllables:          {syllable_count}")
        print(f"Words:              {len(store._word_surfaces)}")
        print(f"Abbreviations:      {store.get_abbreviation_count()}")
        print(f"Phrases:            {phrase_count}")
        print(f"OCR Confusions:     {store.get_ocr_confusion_count()}")
        print(f"Foreign Words:      {len(store._foreign_words)}")

    elif args.lex_subcommand == "lookup":
        word = args.word
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

    elif args.lex_subcommand == "candidates":
        key = args.no_tone_key
        candidates = store.get_syllable_candidates(key)
        if candidates:
            print(f"Candidates for no-tone key: {key!r}")
            print("=" * 40)
            for c in sorted(candidates, key=lambda x: x.score.confidence, reverse=True):
                print(f"  {c.surface:20s}  conf={c.score.confidence:.3f}")
        else:
            print(f"No candidates found for {key!r}")

    elif args.lex_subcommand == "validate":
        from vn_corrector.common.validation import validate_lexicon_file
        from vn_corrector.lexicon.store import _load_json

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
            data = _load_json(filename)
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    # Detect if the first argument matches a known subcommand.
    # If so, create a parser with subparsers; otherwise create a flat parser.
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
