"""Source-level candidate generators for Stage 4."""

from vn_corrector.stage4_candidates.sources.abbreviation import AbbreviationSource
from vn_corrector.stage4_candidates.sources.base import (
    CandidateSourceGenerator,
    IdentitySource,
)
from vn_corrector.stage4_candidates.sources.domain_specific import DomainSpecificSource
from vn_corrector.stage4_candidates.sources.edit_distance import EditDistanceSource
from vn_corrector.stage4_candidates.sources.ocr_confusion import OcrConfusionSource
from vn_corrector.stage4_candidates.sources.phrase_evidence import PhraseEvidenceSource

# original.py re-exports IdentitySource
from vn_corrector.stage4_candidates.sources.syllable_map import SyllableMapSource
from vn_corrector.stage4_candidates.sources.word_lexicon import WordLexiconSource

__all__ = [
    "AbbreviationSource",
    "CandidateSourceGenerator",
    "DomainSpecificSource",
    "EditDistanceSource",
    "IdentitySource",
    "OcrConfusionSource",
    "PhraseEvidenceSource",
    "SyllableMapSource",
    "WordLexiconSource",
]
