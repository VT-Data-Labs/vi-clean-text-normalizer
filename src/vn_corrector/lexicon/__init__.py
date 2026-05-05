"""Lexicon store interface and backends."""

from vn_corrector.lexicon.store import (
    JsonLexiconStore,
    LexiconStore,
    load_default_lexicon,
    load_json_resource,
)

__all__ = [
    "JsonLexiconStore",
    "LexiconStore",
    "SqliteLexiconStore",
    "load_default_lexicon",
    "load_json_resource",
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
