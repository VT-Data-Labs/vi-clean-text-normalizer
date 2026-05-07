"""Stage 2 — Production Lexicon System.

This package provides the canonical knowledge layer of the Vietnamese
text normalisation pipeline.  The production backend is
:class:`~vn_corrector.stage2_lexicon.backends.data_store.LexiconDataStore`.

All lexicon data is loaded into memory at initialisation time.
Runtime correction does **not** read SQLite.

Usage::

    from vn_corrector.stage2_lexicon import load_default_lexicon

    store = load_default_lexicon("hybrid")
    key   = normalize_key("Muỗng")          # "muong"
    result = store.lookup(key)              # accent-insensitive match
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from vn_corrector.stage2_lexicon.backends.data_store import LexiconDataStore
from vn_corrector.stage2_lexicon.core.store import LexiconStore

_DEFAULT_DB_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "data" / "lexicon" / "trusted_lexicon.db"
)


def load_default_lexicon(
    mode: Literal["json", "sqlite", "hybrid", "memory"] = "hybrid",
    *,
    db_path: str | Path | None = None,
    fallback_to_json: bool = False,
) -> LexiconStore:
    """Load a lexicon store with the requested backend mode.

    All modes return an in-memory :class:`LexiconDataStore`.
    SQLite is only used as a data import source, never queried at runtime.

    Parameters
    ----------
    mode:
        - ``"json"`` — JSON resources only.
        - ``"sqlite"`` — SQLite trusted lexicon only.
        - ``"hybrid"`` (*default*) — JSON resources + SQLite merged.
        - ``"memory"`` — same as ``"hybrid"``.
    db_path:
        Path to SQLite database file (default: ``data/lexicon/trusted_lexicon.db``).
    fallback_to_json:
        If ``True`` and the SQLite DB is not found when mode requires it,
        fall back to JSON only instead of raising.
    """
    db_path = Path(db_path) if db_path else _DEFAULT_DB_PATH

    if mode == "json":
        return LexiconDataStore.from_json()

    if mode == "sqlite":
        if db_path.is_file():
            return LexiconDataStore.from_sqlite(db_path)
        if fallback_to_json:
            return LexiconDataStore.from_json()
        raise FileNotFoundError(
            f"SQLite lexicon DB not found at {db_path}. "
            f"Run ``scripts/build_lexicon_db.py`` first, or use "
            f"``load_default_lexicon(mode='json')`` or set ``fallback_to_json=True``."
        )

    # hybrid / memory — JSON + SQLite merged in-memory
    if db_path.is_file():
        return LexiconDataStore.from_json_and_sqlite(db_path=db_path)
    if fallback_to_json:
        return LexiconDataStore.from_json()
    raise FileNotFoundError(
        f"SQLite lexicon DB not found at {db_path} (required for hybrid mode). "
        f"Run ``scripts/build_lexicon_db.py`` first, or set ``fallback_to_json=True``."
    )


__all__ = [
    "LexiconDataStore",
    "LexiconStore",
    "load_default_lexicon",
]
