"""Core types for the Stage-2 lexicon system.

Adds the following to the shared types in ``vn_corrector.common.types``:

- :class:`LexiconIndex` — formal data / index separation.
- :class:`LexiconMetadata` — versioning / provenance metadata.
- :class:`LexiconBuildStats` — build output statistics.
- :class:`BuildConfig` — configuration for a build pipeline run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypeVar

from vn_corrector.common.types import (
    LexiconEntry,
    LexiconKind,
    LexiconRecord,
    LexiconSource,
    Provenance,
)

EntryT = TypeVar("EntryT", bound=LexiconRecord)

# ---------------------------------------------------------------------------
# LexiconIndex — separates raw data from derived indexes
# ---------------------------------------------------------------------------


@dataclass
class LexiconIndex:
    """Pre-computed indexes over a collection of :class:`LexiconEntry` records.

    Every store that implements :class:`~vn_corrector.stage2_lexicon.core.store.LexiconStore`
    **should** maintain one of these to provide O(1) lookups.

    Attributes
    ----------
    by_surface:
        Surface form → matching entries (typically 0-1 for single-syllable entries).
    by_normalized:
        Normalised (accentless, lowercase) key → matching entries.
    by_kind:
        Lexicon kind → entries of that kind.
    """

    by_surface: dict[str, list[LexiconEntry]] = field(default_factory=dict)
    by_normalized: dict[str, list[LexiconEntry]] = field(default_factory=dict)
    by_kind: dict[LexiconKind, list[LexiconEntry]] = field(default_factory=dict)

    # -- Convenience accessors --------------------------------------------

    def entries_by_surface(self, surface: str) -> list[LexiconEntry]:
        """Return entries whose surface matches *surface* exactly."""
        return self.by_surface.get(surface, [])

    def entries_by_normalized(self, key: str) -> list[LexiconEntry]:
        """Return entries whose normalised key matches *key*."""
        return self.by_normalized.get(key, [])

    def entries_by_kind(self, kind: LexiconKind) -> list[LexiconEntry]:
        """Return all entries of a given *kind*."""
        return self.by_kind.get(kind, [])

    def total_entries(self) -> int:
        """Return the total number of unique entries (by surface)."""
        return sum(len(v) for v in self.by_surface.values())

    # -- Bulk build --------------------------------------------------------

    @classmethod
    def build(cls, entries: list[LexiconEntry]) -> LexiconIndex:
        """Build an index from a flat list of entries.

        Parameters
        ----------
        entries:
            The full entry list to index.

        Returns
        -------
        LexiconIndex
            A fully populated index.
        """
        idx = cls()
        for e in entries:
            idx.by_surface.setdefault(e.surface, []).append(e)
            idx.by_normalized.setdefault(e.no_tone, []).append(e)
            idx.by_kind.setdefault(e.kind, []).append(e)
        return idx


# ---------------------------------------------------------------------------
# Versioning / metadata
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LexiconMetadata:
    """Versioning and provenance metadata for a built lexicon.

    Serialises to JSON as part of the package metadata so that consumers
    can verify they are using the expected version of the knowledge base.
    """

    version: str = ""
    source: str = ""
    builder: str = ""
    stats: LexiconBuildStats | None = None
    provenance: Provenance | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialise this metadata to a JSON-compatible dictionary."""
        base: dict[str, Any] = {
            "version": self.version,
            "source": self.source,
            "builder": self.builder,
        }
        if self.stats is not None:
            base["stats"] = self.stats.to_dict()
        if self.provenance is not None:
            base["provenance"] = {
                "source": str(self.provenance.source.value) if self.provenance.source else None,
                "source_name": self.provenance.source_name,
                "version": self.provenance.version,
            }
        if self.extra:
            base["extra"] = self.extra
        return base


# ---------------------------------------------------------------------------
# Build statistics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LexiconBuildStats:
    """Aggregated statistics for a single build run."""

    total_entries: int = 0
    total_surfaces: int = 0
    total_unique_normalized: int = 0
    by_kind: dict[str, int] = field(default_factory=dict)
    domain_coverage: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        return {
            "total_entries": self.total_entries,
            "total_surfaces": self.total_surfaces,
            "total_unique_normalized": self.total_unique_normalized,
            "by_kind": dict(self.by_kind),
            "domain_coverage": dict(self.domain_coverage),
        }


# ---------------------------------------------------------------------------
# Builder protocol types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BuilderInput:
    """Wrapped input for a :class:`LexiconBuilder`."""

    name: str
    data: Any  # raw data — list[dict], list[str], corpus path, etc.
    source: LexiconSource = LexiconSource.CORPUS
    version: str = ""


@dataclass(frozen=True)
class BuilderOutput[EntryT]:
    """Wrapped output from a :class:`LexiconBuilder`.

    Type parameter *E* is the entry type produced by the builder
    (e.g. ``LexiconEntry``, ``PhraseEntry``, ``OcrConfusionEntry``).
    """

    name: str
    entries: tuple[EntryT, ...]
    metadata: LexiconMetadata | None = None


# ---------------------------------------------------------------------------
# Build configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BuildConfig:
    """Configuration for a full lexicon build pipeline run."""

    version: str = "0.1.0"
    source_name: str = "built-in"
    corpus_path: str | None = None
    exporters: tuple[str, ...] = ("json",)
    output_dir: str = "resources/lexicons"
    validate: bool = True
    extra: dict[str, Any] = field(default_factory=dict)
