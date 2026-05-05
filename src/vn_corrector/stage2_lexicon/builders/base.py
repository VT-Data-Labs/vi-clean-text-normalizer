"""Abstract :class:`LexiconBuilder` contract.

Every builder in the system must implement this interface, ensuring
that data ingestion is deterministic, traceable, and validated before
it enters the lexicon store.

Type parameter *E* specifies the entry type the builder produces
(e.g. ``LexiconEntry``, ``PhraseEntry``, ``OcrConfusionEntry``).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic

from vn_corrector.stage2_lexicon.core.types import BuilderInput, BuilderOutput, EntryT


class LexiconBuilder(ABC, Generic[EntryT]):  # noqa: UP046
    """Abstract base class for all lexicon builders.

    Usage::

        class SyllableBuilder(LexiconBuilder[LexiconEntry]):
            def build(self, input_data: BuilderInput) -> BuilderOutput[LexiconEntry]:
                ...

        builder = SyllableBuilder()
        output: BuilderOutput[LexiconEntry] = builder.build(...)
    """

    @abstractmethod
    def build(self, input_data: BuilderInput) -> BuilderOutput[EntryT]:
        """Build entries from raw *input_data*.

        Parameters
        ----------
        input_data:
            Wrapped raw input containing the data source, version info,
            and provenance.

        Returns
        -------
        BuilderOutput[EntryT]
            A validated, ordered, deduplicated list of entries
            together with build metadata.
        """

    @abstractmethod
    def validate_output(self, entries: list[EntryT]) -> list[str]:
        """Validate builder output, returning a list of error messages.

        An empty list means the output is valid.
        """

    @staticmethod
    def default_source() -> str:
        """Return the default source name for builders of this type."""
        return "built-in"
