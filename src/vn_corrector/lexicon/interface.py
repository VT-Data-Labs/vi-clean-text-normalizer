"""Abstract interface for lexicon stores."""

from __future__ import annotations

from abc import ABC, abstractmethod

from vn_corrector.lexicon.types import (
    LexiconEntry,
    LexiconLookupResult,
    OcrConfusionLookupResult,
    PhraseEntry,
)


class LexiconStoreInterface(ABC):
    @abstractmethod
    def lookup(self, text: str) -> LexiconLookupResult: ...
    @abstractmethod
    def lookup_accentless(self, text: str) -> LexiconLookupResult: ...
    @abstractmethod
    def lookup_abbreviation(self, text: str) -> LexiconLookupResult: ...
    @abstractmethod
    def lookup_phrase(self, text: str) -> list[PhraseEntry]: ...
    @abstractmethod
    def lookup_phrase_str(self, text: str) -> str | None: ...
    @abstractmethod
    def lookup_phrase_normalized(self, text: str) -> list[PhraseEntry]: ...
    @abstractmethod
    def lookup_ocr(self, text: str) -> list[str]: ...
    @abstractmethod
    def get_ocr_corrections(self, text: str) -> OcrConfusionLookupResult: ...
    @abstractmethod
    def get_syllable_candidates(self, no_tone_key: str) -> list[LexiconEntry]: ...
    @abstractmethod
    def contains_word(self, text: str) -> bool: ...
    @abstractmethod
    def contains_syllable(self, text: str) -> bool: ...
    @abstractmethod
    def is_protected_token(self, text: str) -> bool: ...

    def query_prefix(self, _prefix: str) -> list[LexiconEntry] | None:
        return None
