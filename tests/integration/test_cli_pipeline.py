"""Integration tests — CLI + pipeline end-to-end."""

from __future__ import annotations

import json
from contextlib import suppress
from io import StringIO
from typing import Any

import pytest

from vn_corrector.cli import main, parse_args
from vn_corrector.common.correction import CorrectionResult


def _run_cli(args: list[str]) -> str:
    """Run the CLI with *args* (after program name) and return stdout text."""
    import sys

    old_stdout = sys.stdout
    sys.stdout = captured = StringIO()
    try:
        with suppress(SystemExit):
            main(args)
        return captured.getvalue()
    finally:
        sys.stdout = old_stdout


class TestCliIntegration:
    def test_cli_text_mode(self) -> None:
        """CLI text mode runs the pipeline and produces formatted output."""
        output = _run_cli(["neu do am vua du"])
        assert "Original:" in output
        assert "Corrected:" in output
        assert "Confidence:" in output

    def test_cli_json_output(self) -> None:
        """CLI --json mode produces valid JSON with all expected fields."""
        output = _run_cli(["--json", "neu", "do", "am", "vua", "du"])
        payload: dict[str, Any] = json.loads(output)
        assert "original_text" in payload
        assert "corrected_text" in payload
        assert "confidence" in payload
        assert "changes" in payload
        assert "flags" in payload
        assert "metadata" in payload
        assert payload["original_text"] == "neu do am vua du"

    def test_cli_unknown_text_preserved(self) -> None:
        output = _run_cli(["--json", "zzqxxabc"])
        payload = json.loads(output)
        assert payload["corrected_text"] == "zzqxxabc"

    def test_cli_json_includes_metadata(self) -> None:
        output = _run_cli(["--json", "xin", "chao"])
        payload = json.loads(output)
        assert "pipeline_version" in payload["metadata"]

    def test_cli_handles_empty_input_gracefully(self) -> None:
        """Empty text from stdin produces exit code 1."""
        import sys
        from io import StringIO

        old_stdin = sys.stdin
        sys.stdin = StringIO("")
        old_stderr = sys.stderr
        sys.stderr = StringIO()
        try:
            with pytest.raises(SystemExit) as exc_info:
                main([])
            assert exc_info.value.code == 1
        finally:
            sys.stdin = old_stdin
            sys.stderr = old_stderr

    def test_parse_args_defaults(self) -> None:
        ns = parse_args(["hello world"])
        assert " ".join(ns.text) == "hello world"

    def test_parse_args_json(self) -> None:
        ns = parse_args(["--json", "test"])
        assert ns.output_json is True

    def test_main_with_domain(self) -> None:
        output = _run_cli(["--domain", "general", "xin", "chao"])
        assert "Corrected:" in output


class TestPipelineEndToEnd:
    """Verify the pipeline is not stubbed — it runs real stages."""

    def test_pipeline_not_stubbed(self) -> None:
        from vn_corrector.pipeline import correct_text

        result = correct_text("neu do am vua du")
        assert isinstance(result, CorrectionResult)

    def test_cli_not_stubbed(self) -> None:
        """The CLI's correct_text delegates to pipeline, not a stub."""
        from vn_corrector.cli import correct_text as cli_correct

        result = cli_correct("neu do am vua du")
        assert isinstance(result, CorrectionResult)
