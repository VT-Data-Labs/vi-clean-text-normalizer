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

from vn_corrector.common.types import CorrectionResult


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
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
    return parser.parse_args(argv)


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
        changes=[],
        flags=[],
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
            lines.append(f"  [{c.start}:{c.end}] {c.original!r} → {c.replacement!r}")
    if result.flags:
        lines.append("Flags:")
        for f in result.flags:
            lines.append(f"  {f.type}: {f.span!r} — {f.reason}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    if args.interactive:
        print("Interactive mode. Enter text (Ctrl-D to exit):", file=sys.stderr)
        for line in sys.stdin:
            line = line.rstrip("\n")
            if not line:
                continue
            result = correct_text(line, args.domain)
            if args.output_json:
                print(json.dumps(asdict(result), ensure_ascii=False))
            else:
                print(format_output(result))
                print()
        return

    text = " ".join(args.text) if args.text else sys.stdin.read().strip()

    if not text:
        print("Error: no input text provided.", file=sys.stderr)
        sys.exit(1)

    result = correct_text(text, args.domain)

    if args.output_json:
        print(json.dumps(asdict(result), ensure_ascii=False))
    else:
        print(format_output(result))


if __name__ == "__main__":
    main()
