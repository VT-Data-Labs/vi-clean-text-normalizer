"""Lexicon store — enhanced abstract interface.

Extends the existing :class:`~vn_corrector.common.lexicon.LexiconStoreInterface` ABC
with new methods required by M3-M5 integration:

- :meth:`is_protected_token` — bridges M2 → M3.
- :meth:`get_lexicon_index` — exposes the formal :class:`~.types.LexiconIndex`.

Backward compatibility is maintained: all existing abstract methods from the
original :class:`~vn_corrector.common.lexicon.LexiconStoreInterface` are preserved.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from vn_corrector.common.lexicon import (
    AbbreviationEntry,
    LexiconEntry,
    LexiconLookupResult,
    LexiconStoreInterface,
    OcrConfusionLookupResult,
    PhraseEntry,
)
from vn_corrector.stage2_lexicon.core.normalize import normalize_key
from vn_corrector.stage2_lexicon.core.types import LexiconIndex

if TYPE_CHECKING:
    from vn_corrector.stage2_lexicon.backends.json_store import JsonLexiconStore


# ---------------------------------------------------------------------------
# Enhanced abstract interface
# ---------------------------------------------------------------------------


class LexiconStore(LexiconStoreInterface, ABC):
    """Enhanced abstract interface for a Vietnamese lexicon store.

    All backends (:class:`~vn_corrector.stage2_lexicon.backends.json_store.JsonLexiconStore`,
    :class:`~vn_corrector.stage2_lexicon.backends.sqlite_store.SqliteLexiconStore`)
    must implement this interface.

    Every lookup **must** use :func:`normalize_key` for accent-insensitive
    matching to guarantee deterministic behaviour.
    """

    # -- Core new methods --------------------------------------------------

    @abstractmethod
    def is_protected_token(self, text: str) -> bool:
        """Return ``True`` if *text* is a protected token.

        Protected tokens include foreign words, chemical terms, brand names,
        codes, and any other entries that must not be modified by the
        correction pipeline.

        This bridges M2 → M3 so that :class:`~vn_corrector.stage3_protect`
        can query the lexicon for protected spans.
        """

    @abstractmethod
    def get_lexicon_index(self) -> LexiconIndex:
        """Return the formal :class:`LexiconIndex` for this store.

        The index provides O(1) lookup by surface, normalised key, and kind.
        """

    # -- Surface / exact lookups (preserved) ------------------------------

    @abstractmethod
    def lookup(self, text: str) -> LexiconLookupResult:
        """Look up *text* by exact surface form (syllables, words, abbreviations)."""

    @abstractmethod
    def lookup_syllable(self, text: str) -> list[str]:
        """Return syllable candidate surfaces for *text* (accent-insensitive)."""

    @abstractmethod
    def lookup_unit(self, text: str) -> list[LexiconEntry]:
        """Return unit entries whose surface exactly matches *text*."""

    @abstractmethod
    def lookup_abbreviation(self, text: str) -> LexiconLookupResult:
        """Look up an abbreviation by its surface form."""

    @abstractmethod
    def lookup_phrase(self, text: str) -> list[PhraseEntry]:
        """Look up phrase entries by exact surface form."""

    @abstractmethod
    def lookup_phrase_str(self, text: str) -> str | None:
        """Look up a phrase by its no-tone form, return the accented surface or ``None``."""

    # -- Accentless / no-tone lookups (preserved) -------------------------

    @abstractmethod
    def lookup_accentless(self, text: str) -> LexiconLookupResult:
        """Look up *text* by stripped/accentless form (syllables + words)."""

    @abstractmethod
    def lookup_no_tone(self, text: str) -> LexiconLookupResult:
        """Alias for :meth:`lookup_accentless`."""

    @abstractmethod
    def lookup_phrase_normalized(self, text: str) -> list[PhraseEntry]:
        """Look up phrase entries by no-tone (accentless) form."""

    @abstractmethod
    def get_syllable_candidates(self, no_tone_key: str) -> list[LexiconEntry]:
        """Return all syllable entries matching a no-tone key."""

    # -- Prefix search (optional, used by edit-distance fallback) ----------

    def query_prefix(self, _prefix: str) -> list[LexiconEntry] | None:
        """Return entries whose no-tone key starts with *prefix*.

        Optional — backends that do not support prefix search return
        ``None``.  The caller (EditDistanceSource) falls back to
        ``lookup_accentless`` in that case.
        """
        return None

    # -- OCR confusion (preserved) ----------------------------------------

    @abstractmethod
    def lookup_ocr(self, noisy: str) -> list[str]:
        """Return known correction surfaces for a noisy OCR token."""

    @abstractmethod
    def get_ocr_corrections(self, noisy: str) -> OcrConfusionLookupResult:
        """Get known corrections for a noisy OCR token as structured result."""

    @abstractmethod
    def get_all_ocr_confusions(self) -> dict[str, list[str]]:
        """Return the full OCR confusion map (noisy → correction surfaces)."""

    # -- Membership (preserved) -------------------------------------------

    @abstractmethod
    def contains_word(self, text: str) -> bool:
        """Return ``True`` if *text* is a known word or unit (exact surface)."""

    @abstractmethod
    def contains_syllable(self, text: str) -> bool:
        """Return ``True`` if *text* is a known syllable (exact surface)."""

    @abstractmethod
    def contains_foreign_word(self, text: str) -> bool:
        """Return ``True`` if *text* is in the foreign-word list."""

    # -- Aggregate / statistics (preserved) -------------------------------

    @abstractmethod
    def get_abbreviation_entries(self) -> list[AbbreviationEntry]:
        """Return all abbreviation entries."""

    @abstractmethod
    def get_abbreviation_count(self) -> int:
        """Return the number of abbreviation entries."""

    @abstractmethod
    def get_phrase_count(self) -> int:
        """Return the number of unique phrase no-tone keys."""

    @abstractmethod
    def get_ocr_confusion_count(self) -> int:
        """Return the number of OCR confusion entries."""

    @abstractmethod
    def get_syllable_entry_count(self) -> int:
        """Return the total number of individual syllable entries."""

    @abstractmethod
    def get_word_count(self) -> int:
        """Return the number of known word/unit surface forms."""

    @abstractmethod
    def get_foreign_word_count(self) -> int:
        """Return the number of foreign-word entries."""

    # -- Lifecycle (preserved) --------------------------------------------

    def close(self) -> None:
        """Release any resources held by this store (no-op by default)."""
        return None

    # -- Convenience constructors -----------------------------------------

    @classmethod
    def load_default(cls) -> JsonLexiconStore:
        """Load all built-in JSON resources and return a store.

        This is a concrete convenience method so that consumers can write
        ``LexiconStore.load_default()`` without importing a specific backend.

        .. deprecated::
            Use ``load_default_lexicon("json")`` or ``load_default_lexicon("sqlite")``
            for explicit backend selection.
        """
        from vn_corrector.stage2_lexicon.backends.json_store import JsonLexiconStore

        return JsonLexiconStore.from_resources()


__all__ = [
    "LexiconStore",
    "normalize_key",
]
