"""Lexicon store interface and backends.

This module provides backward-compatible imports.
New code should prefer importing from ``vn_corrector.stage2_lexicon``
for the enhanced API (``normalize_key``, ``LexiconIndex``, builders, pipeline).
"""

from vn_corrector.lexicon.store import (
    JsonLexiconStore,
    LexiconStore,
    load_default_lexicon,
    load_json_resource,
)

# Re-export new-stage API for discoverability.
from vn_corrector.stage2_lexicon.core.normalize import normalize_key
from vn_corrector.stage2_lexicon.core.types import LexiconIndex
from vn_corrector.stage2_lexicon.pipeline import build_all

__all__ = [
    "JsonLexiconStore",
    "LexiconIndex",
    "LexiconStore",
    "build_all",
    "load_default_lexicon",
    "load_json_resource",
    "normalize_key",
]


def __getattr__(name: str) -> object:
    """Lazy-import :class:`SqliteLexiconStore` on first access.

    This avoids import failures on systems without the ``sqlite3`` module,
    which is optional but recommended.
    """
    if name == "SqliteLexiconStore":
        from vn_corrector.lexicon.backends import SqliteLexiconStore

        return SqliteLexiconStore
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Include lazy-loaded names in ``dir()``."""
    return [*__all__, "SqliteLexiconStore"]
