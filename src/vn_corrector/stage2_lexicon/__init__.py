"""Stage 2 — Production Lexicon System.

This package provides the canonical knowledge layer of the Vietnamese
text normalisation pipeline:

-   **core** — abstract interfaces, types, index, and normalisation.
-   **backends** — concrete stores (JSON / SQLite / Hybrid).
-   **builders** — scalable data-ingestion components.
-   **pipeline** — orchestrates builds, versioning, and export.

Usage::

    from vn_corrector.stage2_lexicon import load_default_lexicon

    store = load_default_lexicon("sqlite", db_path="data/lexicon/trusted_lexicon.db")
    key   = normalize_key("Muỗng")          # "muong"
    result = store.lookup(key)              # accent-insensitive match
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from vn_corrector.stage2_lexicon.backends.hybrid_store import HybridLexiconStore
from vn_corrector.stage2_lexicon.backends.json_store import JsonLexiconStore
from vn_corrector.stage2_lexicon.backends.sqlite_store import SqliteLexiconStore
from vn_corrector.stage2_lexicon.core.store import LexiconStore

_DEFAULT_RESOURCE_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent / "resources" / "lexicons"
)
_DEFAULT_DB_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "data" / "lexicon" / "trusted_lexicon.db"
)


def load_default_lexicon(
    mode: Literal["json", "sqlite", "hybrid"] = "sqlite",
    *,
    resource_dir: str | Path | None = None,
    db_path: str | Path | None = None,
    fallback_to_json: bool = False,
) -> LexiconStore:
    """Load a lexicon store with the requested backend mode.

    Parameters
    ----------
    mode:
        - ``"json"`` — :class:`JsonLexiconStore` (in-memory, JSON resources only).
        - ``"sqlite"`` — :class:`SqliteLexiconStore` (SQLite, requires pre-built DB).
        - ``"hybrid"`` — :class:`HybridLexiconStore` (SQLite primary + JSON fallback).
    resource_dir:
        Path to JSON resource files (default: ``resources/lexicons/``).
    db_path:
        Path to SQLite database file (default: ``data/lexicon/trusted_lexicon.db``).
    fallback_to_json:
        If ``True`` and ``mode="sqlite"`` but no DB found, fall back to JSON
        instead of raising.

    Returns
    -------
    LexiconStore
        A fully loaded store matching the requested mode.

    Raises
    ------
    FileNotFoundError
        If ``mode="sqlite"`` and the DB file does not exist and
        ``fallback_to_json`` is ``False``.
    """
    resource_dir = Path(resource_dir) if resource_dir else _DEFAULT_RESOURCE_DIR
    db_path = Path(db_path) if db_path else _DEFAULT_DB_PATH

    if mode == "json":
        return JsonLexiconStore.from_resources()

    if mode == "sqlite":
        if db_path.is_file():
            return SqliteLexiconStore.from_db(db_path)
        if fallback_to_json:
            return JsonLexiconStore.from_resources()
        raise FileNotFoundError(
            f"SQLite lexicon DB not found at {db_path}. "
            f"Run ``scripts/build_lexicon_db.py`` first, or use "
            f"``load_default_lexicon(mode='json')`` or set ``fallback_to_json=True``."
        )

    # mode == "hybrid"
    if db_path.is_file():
        primary: LexiconStore = SqliteLexiconStore.from_db(db_path)
    elif fallback_to_json:
        primary = JsonLexiconStore.from_resources()
    else:
        raise FileNotFoundError(
            f"SQLite lexicon DB not found at {db_path} (required for hybrid mode). "
            f"Run ``scripts/build_lexicon_db.py`` first, or set ``fallback_to_json=True``."
        )
    return HybridLexiconStore(primary=primary, fallback=JsonLexiconStore.from_resources())


__all__ = [
    "HybridLexiconStore",
    "JsonLexiconStore",
    "LexiconStore",
    "SqliteLexiconStore",
    "load_default_lexicon",
]
