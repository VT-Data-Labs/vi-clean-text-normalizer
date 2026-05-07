"""Hybrid lexicon store — explicit primary/fallback composition.

Provides :class:`HybridLexiconStore` which wraps two :class:`LexiconStore`
instances and delegates to the primary first, falling back to the secondary
on misses.
"""

from __future__ import annotations

from vn_corrector.lexicon.types import (
    AbbreviationEntry,
    LexiconEntry,
    LexiconLookupResult,
    OcrConfusionLookupResult,
    PhraseEntry,
)
from vn_corrector.stage2_lexicon.core.store import LexiconStore
from vn_corrector.stage2_lexicon.core.types import LexiconIndex


class HybridLexiconStore(LexiconStore):
    """Explicit composition of a primary and fallback lexicon store.

    Args:
        primary: The primary store; its results always win on conflict.
        fallback: Used when the primary returns no result.
    """

    def __init__(self, primary: LexiconStore, fallback: LexiconStore) -> None:
        self._primary = primary
        self._fallback = fallback

    # -- Properties -----------------------------------------------------------

    @property
    def primary(self) -> LexiconStore:
        """The primary store."""
        return self._primary

    @property
    def fallback(self) -> LexiconStore:
        """The fallback store (used on primary miss)."""
        return self._fallback

    # -- Core new methods -----------------------------------------------------

    def is_protected_token(self, text: str) -> bool:
        if self._primary.is_protected_token(text):
            return True
        return self._fallback.is_protected_token(text)

    def get_lexicon_index(self) -> LexiconIndex:
        pidx = self._primary.get_lexicon_index()
        fidx = self._fallback.get_lexicon_index()
        entries: list[LexiconEntry] = []
        for lst in pidx.by_surface.values():
            entries.extend(lst)
        seen = {e.entry_id for e in entries}
        for lst in fidx.by_surface.values():
            for e in lst:
                if e.entry_id not in seen:
                    entries.append(e)
                    seen.add(e.entry_id)
        return LexiconIndex.build(entries)

    # -- Surface / exact lookups ----------------------------------------------

    def lookup(self, text: str) -> LexiconLookupResult:
        result = self._primary.lookup(text)
        if result.found:
            return result
        return self._fallback.lookup(text)

    def lookup_syllable(self, text: str) -> list[str]:
        result = self._primary.lookup_syllable(text)
        if result:
            return result
        return self._fallback.lookup_syllable(text)

    def lookup_unit(self, text: str) -> list[LexiconEntry]:
        result = self._primary.lookup_unit(text)
        if result:
            return result
        return self._fallback.lookup_unit(text)

    def lookup_abbreviation(self, text: str) -> LexiconLookupResult:
        result = self._primary.lookup_abbreviation(text)
        if result.found:
            return result
        return self._fallback.lookup_abbreviation(text)

    def lookup_phrase(self, text: str) -> list[PhraseEntry]:
        result = self._primary.lookup_phrase(text)
        if result:
            return result
        return self._fallback.lookup_phrase(text)

    def lookup_phrase_str(self, text: str) -> str | None:
        result = self._primary.lookup_phrase_str(text)
        if result is not None:
            return result
        return self._fallback.lookup_phrase_str(text)

    # -- Accentless / no-tone lookups -----------------------------------------

    def lookup_accentless(self, text: str) -> LexiconLookupResult:
        result = self._primary.lookup_accentless(text)
        if result.found:
            return result
        return self._fallback.lookup_accentless(text)

    def lookup_no_tone(self, text: str) -> LexiconLookupResult:
        return self.lookup_accentless(text)

    def lookup_phrase_normalized(self, text: str) -> list[PhraseEntry]:
        result = self._primary.lookup_phrase_normalized(text)
        if result:
            return result
        return self._fallback.lookup_phrase_normalized(text)

    def get_syllable_candidates(self, no_tone_key: str) -> list[LexiconEntry]:
        primary = self._primary.get_syllable_candidates(no_tone_key)
        fallback = self._fallback.get_syllable_candidates(no_tone_key)
        seen = {e.entry_id for e in primary}
        merged = list(primary)
        for e in fallback:
            if e.entry_id not in seen:
                merged.append(e)
                seen.add(e.entry_id)
        return merged

    # -- OCR confusion --------------------------------------------------------

    def lookup_ocr(self, noisy: str) -> list[str]:
        result = self._primary.lookup_ocr(noisy)
        if result:
            return result
        return self._fallback.lookup_ocr(noisy)

    def get_ocr_corrections(self, noisy: str) -> OcrConfusionLookupResult:
        result = self._primary.get_ocr_corrections(noisy)
        if result.found:
            return result
        return self._fallback.get_ocr_corrections(noisy)

    def get_all_ocr_confusions(self) -> dict[str, list[str]]:
        result = dict(self._primary.get_all_ocr_confusions())
        for k, v in self._fallback.get_all_ocr_confusions().items():
            if k not in result:
                result[k] = v
        return result

    # -- Membership -----------------------------------------------------------

    def contains_word(self, text: str) -> bool:
        if self._primary.contains_word(text):
            return True
        return self._fallback.contains_word(text)

    def contains_syllable(self, text: str) -> bool:
        if self._primary.contains_syllable(text):
            return True
        return self._fallback.contains_syllable(text)

    def contains_foreign_word(self, text: str) -> bool:
        if self._primary.contains_foreign_word(text):
            return True
        return self._fallback.contains_foreign_word(text)

    # -- Aggregate / statistics -----------------------------------------------

    def get_abbreviation_entries(self) -> list[AbbreviationEntry]:
        p_entries = self._primary.get_abbreviation_entries()
        f_entries = self._fallback.get_abbreviation_entries()
        seen = {e.entry_id for e in p_entries}
        merged = list(p_entries)
        for e in f_entries:
            if e.entry_id not in seen:
                merged.append(e)
                seen.add(e.entry_id)
        return merged

    def get_abbreviation_count(self) -> int:
        return self._primary.get_abbreviation_count() + self._fallback.get_abbreviation_count()

    def get_phrase_count(self) -> int:
        return self._primary.get_phrase_count() + self._fallback.get_phrase_count()

    def get_ocr_confusion_count(self) -> int:
        return self._primary.get_ocr_confusion_count() + self._fallback.get_ocr_confusion_count()

    def get_syllable_entry_count(self) -> int:
        return self._primary.get_syllable_entry_count() + self._fallback.get_syllable_entry_count()

    def get_word_count(self) -> int:
        return self._primary.get_word_count() + self._fallback.get_word_count()

    def get_foreign_word_count(self) -> int:
        return self._primary.get_foreign_word_count() + self._fallback.get_foreign_word_count()

    # -- Lifecycle ------------------------------------------------------------

    def close(self) -> None:
        self._primary.close()
        self._fallback.close()


__all__ = [
    "HybridLexiconStore",
]
