"""ABC interface for the n-gram store backend."""

from __future__ import annotations

from abc import ABC, abstractmethod


class NgramStore(ABC):
    """Abstract n-gram store providing phrase-level scoring queries.

    Concrete backends (JSON, SQLite, etc.) implement these methods.
    Missing keys must return ``0.0``, never raise.
    """

    @abstractmethod
    def bigram_score(self, w1: str, w2: str) -> float:
        """Score for the bigram ``w1 w2`` (0.0 if absent)."""
        ...

    @abstractmethod
    def trigram_score(self, w1: str, w2: str, w3: str) -> float:
        """Score for the trigram ``w1 w2 w3`` (0.0 if absent)."""
        ...

    @abstractmethod
    def fourgram_score(self, w1: str, w2: str, w3: str, w4: str) -> float:
        """Score for the fourgram ``w1 w2 w3 w4`` (0.0 if absent)."""
        ...

    @abstractmethod
    def phrase_score(self, tokens: tuple[str, ...]) -> float:
        """Score for a full-phrase lookup (any token count).

        Delegates to the appropriate n-gram method based on token count
        when possible, or returns 0.0 for unindexed lengths.
        """
        ...

    @abstractmethod
    def domain_phrase_score(self, domain: str, tokens: tuple[str, ...]) -> float:
        """Score for *tokens* restricted to *domain* (0.0 if absent)."""
        ...

    @abstractmethod
    def negative_phrase_score(self, tokens: tuple[str, ...]) -> float:
        """Penalty score for a known-bad sequence (0.0 if absent)."""
        ...
