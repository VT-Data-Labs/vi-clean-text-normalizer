"""YAML-driven matcher registry.

Loads matcher configurations from YAML files and instantiates the
appropriate ``Matcher`` subclass (``RegexMatcher`` or ``LexiconMatcher``).

Usage::

    matchers = load_matchers("resources/matchers")
    doc = protect("Hello 120ml world", matchers)
"""

from __future__ import annotations

import pathlib
from typing import Any

import yaml

from vn_corrector.common.enums import SpanType
from vn_corrector.stage3_protect.matchers.base import Matcher
from vn_corrector.stage3_protect.matchers.lexicon import LexiconMatcher
from vn_corrector.stage3_protect.matchers.regex import RegexMatcher

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_matchers(config_dir: str | pathlib.Path) -> list[Matcher]:
    """Load all matcher YAML files from *config_dir*.

    Each ``.yaml`` file must contain a dict with at minimum:
        name (str)
        type (str)         — ``"regex"`` or ``"lexicon"``
        priority (int)
        span_type (str)    — one of the ``SpanType`` enum values

    Regex matchers additionally require:
        patterns (list[str])

    Lexicon matchers additionally require:
        source (str)       — path to a text file (one entry per line)

    Returns a list sorted by priority (descending) so that higher-priority
    matchers run first during ``protect()``.
    """
    config_path = pathlib.Path(config_dir)
    if not config_path.is_dir():
        raise NotADirectoryError(f"Matcher config directory not found: {config_dir}")

    matchers: list[Matcher] = []

    for yaml_path in sorted(config_path.glob("*.yaml")):
        with open(yaml_path, encoding="utf-8") as fh:
            config: dict[str, Any] = yaml.safe_load(fh)

        if not isinstance(config, dict):
            continue

        matcher = _create_matcher(config, yaml_path.parent)
        if matcher is not None:
            matchers.append(matcher)

    # Highest priority first — useful for debugging iteration order
    matchers.sort(key=lambda m: m.priority, reverse=True)
    return matchers


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _create_matcher(
    config: dict[str, Any],
    config_dir: pathlib.Path,
) -> Matcher | None:
    """Instantiate a single Matcher from its YAML config dict."""
    name: str = config.get("name", "")
    matcher_type: str = config.get("type", "")
    priority: int = config.get("priority", 0)

    span_type_raw: str = config.get("span_type", name)

    # Convert string span_type to SpanType enum.
    try:
        span_type = SpanType(span_type_raw)
    except ValueError:
        return None

    if matcher_type == "regex":
        patterns: list[str] = config.get("patterns", [])
        require_ascii: bool = config.get("require_ascii", False)

        if not patterns:
            return None

        return RegexMatcher(
            name=name,
            priority=priority,
            span_type=span_type,
            patterns=patterns,
            require_ascii=require_ascii,
        )

    if matcher_type == "lexicon":
        source: str = config.get("source", "")
        case_sensitive: bool = config.get("case_sensitive", True)

        if not source:
            return None

        # Resolve source relative to the config directory.
        source_path = pathlib.Path(source)
        if not source_path.is_absolute():
            source_path = config_dir / source

        if not source_path.is_file():
            return None

        lexicon = LexiconMatcher.load_from_file(str(source_path))

        if not lexicon:
            return None

        return LexiconMatcher(
            name=name,
            priority=priority,
            span_type=span_type,
            lexicon=lexicon,
            case_sensitive=case_sensitive,
        )

    return None
