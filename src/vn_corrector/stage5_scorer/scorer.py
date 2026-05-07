"""PhraseScorer — score candidate sequences using multiple signals."""

from __future__ import annotations

from vn_corrector.lexicon.interface import LexiconStoreInterface
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
        for i in range(len(tokens) - 1):
            score += ns.bigram_score(tokens[i], tokens[i + 1])
        for i in range(len(tokens) - 2):
            score += ns.trigram_score(tokens[i], tokens[i + 1], tokens[i + 2])
        for i in range(len(tokens) - 3):
            score += ns.fourgram_score(
                tokens[i],
                tokens[i + 1],
                tokens[i + 2],
                tokens[i + 3],
            )
        return score

    def _score_domain_context(self, tokens: tuple[str, ...], domain: str | None) -> float:
        if not domain or not self._config.enable_domain_context:
            return 0.0
        return self._ngram_store.domain_phrase_score(domain, tokens)

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
        changed_valid = 0
        total = 0
        for token, orig in zip(tokens, original_tokens, strict=False):
            if token == orig:
                continue
            total += 1
            if self._lexicon.contains_word(orig):
                changed_valid += 1
        if total == 0:
            return 0.0
        return changed_valid / total

    def _score_negative_phrase_penalty(self, tokens: tuple[str, ...]) -> float:
        return self._ngram_store.negative_phrase_score(tokens)

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
