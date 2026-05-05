"""Stage 2 — Production Lexicon System.

This package provides the canonical knowledge layer of the Vietnamese
text normalisation pipeline:

-   **core** — abstract interfaces, types, index, and normalisation.
-   **backends** — concrete stores (JSON / SQLite).
-   **builders** — scalable data-ingestion components.
-   **pipeline** — orchestrates builds, versioning, and export.

Usage::

    from vn_corrector.stage2_lexicon.core.normalize import normalize_key
    from vn_corrector.stage2_lexicon.backends import JsonLexiconStore

    store = JsonLexiconStore.load_default()
    key   = normalize_key("Muỗng")          # "muong"
    result = store.lookup(key)              # accent-insensitive match
"""

from vn_corrector.stage2_lexicon.backends.json_store import JsonLexiconStore
from vn_corrector.stage2_lexicon.backends.sqlite_store import SqliteLexiconStore
from vn_corrector.stage2_lexicon.core.store import LexiconStore

__all__ = [
    "JsonLexiconStore",
    "LexiconStore",
    "SqliteLexiconStore",
]
