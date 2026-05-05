"""Lexicon builders — scalable data-ingestion components.

Each builder implements the :class:`LexiconBuilder` contract and consumes
raw input data (corpora, rule files, domain lists) to produce validated
:class:`~vn_corrector.common.types.LexiconEntry` lists.

Builders
--------
- :mod:`base` — abstract :class:`LexiconBuilder` contract.
- :mod:`syllables` — syllable builder (base → accented forms).
- :mod:`words` — multi-syllable word builder.
- :mod:`phrases` — n-gram phrase builder.
- :mod:`confusion` — OCR confusion map builder.
- :mod:`abbreviations` — abbreviation builder.
"""

from vn_corrector.stage2_lexicon.builders.abbreviations import AbbreviationBuilder
from vn_corrector.stage2_lexicon.builders.base import LexiconBuilder
from vn_corrector.stage2_lexicon.builders.confusion import ConfusionBuilder
from vn_corrector.stage2_lexicon.builders.phrases import PhraseBuilder
from vn_corrector.stage2_lexicon.builders.syllables import SyllableBuilder
from vn_corrector.stage2_lexicon.builders.words import WordBuilder

__all__ = [
    "AbbreviationBuilder",
    "ConfusionBuilder",
    "LexiconBuilder",
    "PhraseBuilder",
    "SyllableBuilder",
    "WordBuilder",
]
