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
    """Lazy-import :class:`SqliteLexiconStore` so that the import
    does not fail on systems without ``sqlite3`` support (extremely
    rare, but the backend is genuinely optional)."""
    if name == "SqliteLexiconStore":
        from vn_corrector.lexicon.backends import SqliteLexiconStore

        return SqliteLexiconStore
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
