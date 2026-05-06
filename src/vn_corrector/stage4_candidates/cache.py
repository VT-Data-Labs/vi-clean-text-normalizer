"""In-memory LRU cache for candidate generation results.

Eviction uses true LRU ordering: every ``get()`` hit moves the entry
to the most-recently-used position, and eviction removes from the
least-recently-used (oldest) end.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import cast

from vn_corrector.stage4_candidates.config import CandidateGeneratorConfig
from vn_corrector.stage4_candidates.types import Candidate

# Sentinel for cache misses
_SENTINEL = object()


class TokenCache:
    """LRU in-memory cache for token-level candidate results.

    Caches by ``(token_text, token_type_str, protected, config_fingerprint)``.
    Entries are moved to the most-recently-used position on every hit.
    Eviction removes least-recently-used entries first.
    """

    def __init__(self, maxsize: int = 100_000) -> None:
        self._maxsize = maxsize
        self._store: OrderedDict[tuple[str, str, bool, int], list[Candidate]] = OrderedDict()
        self._hits: int = 0
        self._misses: int = 0

    def _fingerprint(self, config: CandidateGeneratorConfig) -> int:
        """Generate a simple fingerprint from config toggles."""
        try:
            flags = (
                config.enable_original,
                config.enable_ocr_confusion,
                config.enable_syllable_map,
                config.enable_word_lexicon,
                config.enable_abbreviation,
                config.enable_phrase_evidence,
                config.enable_domain_specific,
                config.enable_edit_distance,
                config.max_candidates_per_token,
                config.max_ocr_replacements_per_token,
                config.max_edit_distance,
                config.deterministic_sort,
            )
            return hash(flags)
        except AttributeError:
            return 0

    def get(
        self,
        token_text: str,
        token_type_str: str,
        protected: bool,
        config: CandidateGeneratorConfig,
    ) -> list[Candidate] | None:
        """Look up cached result, returning ``None`` on miss.

        Moves the entry to the most-recently-used position on hit.
        """
        key = (token_text, token_type_str, protected, self._fingerprint(config))
        result = self._store.get(key, _SENTINEL)
        if result is _SENTINEL:
            self._misses += 1
            return None
        self._hits += 1
        self._store.move_to_end(key)  # mark as most recently used
        return cast("list[Candidate]", result)

    def put(
        self,
        token_text: str,
        token_type_str: str,
        protected: bool,
        config: CandidateGeneratorConfig,
        candidates: list[Candidate],
    ) -> None:
        """Store a result in the cache.

        Evicts the least-recently-used entries when at capacity.
        """
        if len(self._store) >= self._maxsize:
            # Evict oldest ~10% of entries (LRU: first items in dict are LRU)
            remove_count = max(1, self._maxsize // 10)
            for _ in range(remove_count):
                if self._store:
                    self._store.pop(next(iter(self._store)))
        key = (token_text, token_type_str, protected, self._fingerprint(config))
        self._store[key] = candidates

    @property
    def hits(self) -> int:
        return self._hits

    @property
    def misses(self) -> int:
        return self._misses

    @property
    def size(self) -> int:
        return len(self._store)

    def clear(self) -> None:
        self._store.clear()
        self._hits = 0
        self._misses = 0


__all__ = ["TokenCache"]
