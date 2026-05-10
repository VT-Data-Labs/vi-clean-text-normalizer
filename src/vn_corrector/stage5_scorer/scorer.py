"""PhraseScorer — score candidate sequences using multiple signals."""

from __future__ import annotations

from vn_corrector.common.lexicon import LexiconStoreInterface
from vn_corrector.stage1_normalize import strip_accents
from vn_corrector.stage4_candidates.types import CandidateSource
from vn_corrector.stage5_scorer.combinations import generate_sequences
from vn_corrector.stage5_scorer.config import PhraseScorerConfig
from vn_corrector.stage5_scorer.ngram_store import NgramStore
from vn_corrector.stage5_scorer.types import (
    CandidateSequence,
    CandidateWindow,
    CorrectionEvidence,
    ScoreBreakdown,
    ScoredSequence,
    ScoredWindow,
    TokenCorrectionExplanation,
)
from vn_corrector.stage5_scorer.weights import ScoringWeights
from vn_corrector.utils.unicode import contains_vietnamese


def _is_accentless_variant_correction(
    original: str,
    candidate: str,
    lexicon: LexiconStoreInterface,
) -> bool:
    """Check if *candidate* is a valid accented variant of accentless *original*.

    Returns ``True`` when all of the following hold:
    1. *original* has zero Vietnamese characters (bare Latin/no-tone form).
    2. *candidate* has at least one Vietnamese character (accented form).
    3. Stripping accents from *candidate* yields *original* (same base).
    4. The lexicon contains at least one accented surface matching *candidate*
       for the accentless key.

    This prevents the overcorrection penalty from blocking legitimate
    diacritic restoration like ``he → hệ`` while still protecting real
    overcorrections like ``anh → ảnh`` when the original already has valid
    Vietnamese meaning.
    """
    if original == candidate:
        return False
    if contains_vietnamese(original):
        return False
    if not contains_vietnamese(candidate):
        return False
    if strip_accents(candidate).lower() != original.lower():
        return False
    result = lexicon.lookup_accentless(original)
    if not result.found or not result.entries:
        return False
    return any(
        hasattr(e, "surface") and e.surface.lower() == candidate.lower() for e in result.entries
    )


def _candidate_improves_ngram(
    candidate: str,
    original: str,
    original_tokens: tuple[str, ...],
    idx: int,
    ngram_store: NgramStore,
    *,
    min_score: float = 0.5,
    min_delta: float = 0.2,
) -> bool:
    """Check if *candidate* has stronger local n-gram evidence than *original*.

    Looks at the immediate left and right **content** bigram contexts
    (skipping whitespace tokens, matching how
    :meth:`PhraseScorer._score_phrase_ngram` builds its content sequence).
    Returns ``True`` when **any** adjacent bigram for *candidate* meets all
    of:

    1. The candidate bigram score ≥ *min_score*.
    2. The candidate bigram score exceeds the original bigram score by at
       least *min_delta*.

    This prevents the overcorrection penalty from blocking legitimate
    context-aware corrections like ``niêm → niềm`` before ``tin`` (where
    *niềm tin* is a known phrase) while still protecting real overcorrections
    on weak/noisy n-gram evidence.
    """
    # Build content-token indices (skip whitespace)
    content_indices = [i for i, t in enumerate(original_tokens) if t.strip()]
    try:
        pos = content_indices.index(idx)
    except ValueError:
        return False

    checks: list[tuple[float, float]] = []

    if pos > 0:
        left_idx = content_indices[pos - 1]
        left = original_tokens[left_idx]
        checks.append(
            (
                ngram_store.bigram_score(left, original),
                ngram_store.bigram_score(left, candidate),
            )
        )

    if pos < len(content_indices) - 1:
        right_idx = content_indices[pos + 1]
        right = original_tokens[right_idx]
        checks.append(
            (
                ngram_store.bigram_score(original, right),
                ngram_store.bigram_score(candidate, right),
            )
        )

    return any(
        cand_score >= min_score and cand_score >= orig_score + min_delta
        for orig_score, cand_score in checks
    )


class PhraseScorer:
    """Score candidate sequences inside a window using multiple signals."""

    def __init__(
        self,
        ngram_store: NgramStore,
        lexicon: LexiconStoreInterface,
        config: PhraseScorerConfig | None = None,
        weights: ScoringWeights | None = None,
    ) -> None:
        self._ngram_store = ngram_store
        self._lexicon = lexicon
        self._config = config or PhraseScorerConfig()
        self._weights = weights or ScoringWeights()

    # -- public API ---------------------------------------------------------

    def score_window(
        self,
        window: CandidateWindow,
        domain: str | None = None,
    ) -> ScoredWindow:
        """Score every candidate sequence in *window* and return ranked results."""
        sequences = generate_sequences(
            window,
            max_combinations=self._config.max_combinations,
            max_per_token=self._config.max_candidates_per_token,
        )
        scored = [self._score_sequence(s, window, domain) for s in sequences]
        scored.sort(key=lambda s: s.score, reverse=True)
        return ScoredWindow(window=window, ranked_sequences=scored)

    # -- internal scoring ---------------------------------------------------

    def _score_sequence(
        self,
        sequence: CandidateSequence,
        window: CandidateWindow,
        domain: str | None = None,
    ) -> ScoredSequence:
        tokens = sequence.tokens
        orig = sequence.original_tokens
        w = self._weights

        word_v = self._score_word_validity(tokens) * w.word_validity
        syl_f = self._score_syllable_freq(tokens) * w.syllable_freq
        phr_n = self._score_phrase_ngram(tokens) * w.phrase_ngram
        dom_c = self._score_domain_context(tokens, domain) * w.domain_context
        ocr_c = self._score_ocr_confusion(tokens, orig, window) * w.ocr_confusion
        edit_d = self._score_edit_distance(tokens, orig, window) * w.edit_distance
        over_p = self._score_overcorrection_penalty(tokens, orig) * w.overcorrection_penalty
        neg_p = self._score_negative_phrase_penalty(tokens) * w.negative_phrase_penalty

        breakdown = ScoreBreakdown(
            word_validity=word_v,
            syllable_freq=syl_f,
            phrase_ngram=phr_n,
            domain_context=dom_c,
            ocr_confusion=ocr_c,
            edit_distance=edit_d,
            overcorrection_penalty=over_p,
            negative_phrase_penalty=neg_p,
        )

        confidence = self._compute_confidence(breakdown)
        explanations = self._build_explanations(sequence, breakdown)

        return ScoredSequence(
            sequence=sequence,
            breakdown=breakdown,
            confidence=confidence,
            explanations=explanations,
        )

    def _score_word_validity(self, tokens: tuple[str, ...]) -> float:
        score = 0.0
        for t in tokens:
            if self._lexicon.contains_word(t):
                score += 1.0
        return score

    def _score_syllable_freq(self, tokens: tuple[str, ...]) -> float:
        score = 0.0
        for t in tokens:
            if self._lexicon.contains_syllable(t):
                score += 0.3
        return score

    def _score_phrase_ngram(self, tokens: tuple[str, ...]) -> float:
        score = 0.0
        ns = self._ngram_store
        content = [t for t in tokens if t.strip()]
        for i in range(len(content) - 1):
            score += ns.bigram_score(content[i], content[i + 1])
        for i in range(len(content) - 2):
            score += ns.trigram_score(content[i], content[i + 1], content[i + 2])
        for i in range(len(content) - 3):
            score += ns.fourgram_score(
                content[i],
                content[i + 1],
                content[i + 2],
                content[i + 3],
            )
        return score

    def _score_domain_context(self, tokens: tuple[str, ...], domain: str | None) -> float:
        if not domain or not self._config.enable_domain_context:
            return 0.0
        content = tuple(t for t in tokens if t.strip())
        return self._ngram_store.domain_phrase_score(domain, content)

    def _score_ocr_confusion(
        self,
        tokens: tuple[str, ...],
        original_tokens: tuple[str, ...],
        window: CandidateWindow,
    ) -> float:
        score = 0.0
        for token, orig in zip(tokens, original_tokens, strict=False):
            if token == orig:
                continue
            for tc in window.token_candidates:
                if tc.token_text != orig:
                    continue
                for cand in tc.candidates:
                    if cand.text == token and CandidateSource.OCR_CONFUSION in cand.sources:
                        score += 1.0
                        break
        return score

    def _score_edit_distance(
        self,
        tokens: tuple[str, ...],
        original_tokens: tuple[str, ...],
        window: CandidateWindow,
    ) -> float:
        score = 0.0
        for token, orig in zip(tokens, original_tokens, strict=False):
            if token == orig:
                score += 1.0
                continue
            for tc in window.token_candidates:
                if tc.token_text != orig:
                    continue
                for cand in tc.candidates:
                    if cand.text == token and cand.edit_distance is not None:
                        score += 1.0 / (1.0 + cand.edit_distance)
                        break
        return score

    def _score_overcorrection_penalty(
        self,
        tokens: tuple[str, ...],
        original_tokens: tuple[str, ...],
    ) -> float:
        penalized_changes = 0
        total = 0
        for i, (token, orig) in enumerate(zip(tokens, original_tokens, strict=False)):
            if token == orig:
                continue
            total += 1
            if not self._lexicon.contains_word(orig):
                continue
            if _is_accentless_variant_correction(orig, token, self._lexicon):
                continue
            if _candidate_improves_ngram(
                token,
                orig,
                original_tokens,
                i,
                self._ngram_store,
            ):
                continue
            penalized_changes += 1
        if total == 0:
            return 0.0
        return penalized_changes / total

    def _score_negative_phrase_penalty(self, tokens: tuple[str, ...]) -> float:
        content = tuple(t for t in tokens if t.strip())
        return self._ngram_store.negative_phrase_score(content)

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _compute_confidence(breakdown: ScoreBreakdown) -> float:
        raw = breakdown.total
        clamped = max(0.0, min(1.0, (raw + 5.0) / 10.0))
        return clamped

    @staticmethod
    def _build_explanations(
        sequence: CandidateSequence,
        breakdown: ScoreBreakdown,
    ) -> list[TokenCorrectionExplanation]:
        explanations: list[TokenCorrectionExplanation] = []
        for pos in sequence.changed_positions:
            orig = sequence.original_tokens[pos]
            corr = sequence.tokens[pos]
            evidence: list[CorrectionEvidence] = []
            if breakdown.ocr_confusion > 0:
                evidence.append(
                    CorrectionEvidence(
                        kind="ocr_confusion",
                        message=f"OCR confusion evidence supports {orig} → {corr}",
                        score_delta=breakdown.ocr_confusion,
                    )
                )
            if breakdown.phrase_ngram > 0:
                evidence.append(
                    CorrectionEvidence(
                        kind="phrase_ngram",
                        message="Phrase n-gram evidence supports this sequence",
                        score_delta=breakdown.phrase_ngram,
                    )
                )
            if breakdown.edit_distance > 0:
                evidence.append(
                    CorrectionEvidence(
                        kind="edit_distance",
                        message="Candidate is close to original",
                        score_delta=breakdown.edit_distance,
                    )
                )
            if breakdown.domain_context > 0:
                evidence.append(
                    CorrectionEvidence(
                        kind="domain_context",
                        message="Domain phrase match",
                        score_delta=breakdown.domain_context,
                    )
                )
            explanations.append(
                TokenCorrectionExplanation(
                    index=pos,
                    original=orig,
                    corrected=corr,
                    evidence=evidence,
                )
            )
        return explanations
