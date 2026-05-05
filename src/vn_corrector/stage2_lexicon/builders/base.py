"""Abstract :class:`LexiconBuilder` contract.

Every builder in the system must implement this interface, ensuring
that data ingestion is deterministic, traceable, and validated before
it enters the lexicon store.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from vn_corrector.stage2_lexicon.core.types import BuilderInput, BuilderOutput


class LexiconBuilder(ABC):
    """Abstract base class for all lexicon builders.

    Usage::

        class MyBuilder(LexiconBuilder):
            def build(self, input_data: BuilderInput) -> BuilderOutput:
                ...

        builder = MyBuilder()
        output = builder.build(BuilderInput(name="my_data", data=[...]))
    """

    @abstractmethod
    def build(self, input_data: BuilderInput) -> BuilderOutput:
        """Build :class:`LexiconEntry` list(s) from raw *input_data*.

        Parameters
        ----------
        input_data:
            Wrapped raw input containing the data source, version info,
            and provenance.

        Returns
        -------
        BuilderOutput
            A validated, ordered, deduplicated list of lexicon entries
            together with build metadata.
        """

    @abstractmethod
    def validate_output(self, entries: list[Any]) -> list[str]:
        """Validate builder output, returning a list of error messages.

        An empty list means the output is valid.
        """

    @staticmethod
    def default_source() -> str:
        """Return the default source name for builders of this type."""
        return "built-in"
