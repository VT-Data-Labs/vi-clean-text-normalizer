"""Stage-2 lexicon backends.

Provides concrete implementations of :class:`LexiconStore
<vn_corrector.stage2_lexicon.core.store.LexiconStore>`:

- :class:`JsonLexiconStore` — in-memory, loaded from JSON resource files.
- :class:`SqliteLexiconStore` — SQLite-backed, for production use.
"""

from vn_corrector.stage2_lexicon.backends.json_store import JsonLexiconStore
from vn_corrector.stage2_lexicon.backends.sqlite_store import SqliteLexiconStore

__all__ = [
    "JsonLexiconStore",
    "SqliteLexiconStore",
]
