from __future__ import annotations

from vn_corrector.common.types import CandidateSource as CommonCandidateSource
from vn_corrector.stage5_scorer.types import ScoredSequence, ScoredWindow
from vn_corrector.stage6_decision.config import DecisionEngineConfig
from vn_corrector.stage6_decision.types import (
    CorrectionDecision,
    DecisionReason,
    DecisionType,
)


class DecisionEngine:
    """Deterministic policy layer for correction decisions.

    Consumes M5 ``ScoredWindow`` output and produces one
    ``CorrectionDecision`` per token position.
    """

    def __init__(self, config: DecisionEngineConfig | None = None) -> None:
        self._config = config or DecisionEngineConfig()

    @property
    def config(self) -> DecisionEngineConfig:
        return self._config

    # -- public API ---------------------------------------------------------

    def decide_window(
        self,
        scored_window: ScoredWindow,
    ) -> list[CorrectionDecision]:
        """Produce one decision per token position in the scored window."""
        window = scored_window.window
        ranked = scored_window.ranked_sequences
        n_tokens = len(window.token_candidates)

        if not ranked:
            return [
                CorrectionDecision(
                    original=tc.token_text,
                    best=None,
                    best_score=0.0,
                    decision=DecisionType.REJECT,
                    reason=DecisionReason.NO_RANKED_SEQUENCE,
                )
                for tc in window.token_candidates
            ]

        decisions: list[CorrectionDecision] = []
        for pos in range(n_tokens):
            tc = window.token_candidates[pos]
            best_seq = ranked[0]
            best_token = best_seq.sequence.tokens[pos]
            best_score = best_seq.confidence
            orig = best_seq.sequence.original_tokens[pos]

            second_token, second_score = _find_second_best_for_position(
                ranked,
                pos,
                best_token,
            )

            candidate_sources = _collect_sources(tc)

            decision = self.decide_token(
                original=orig,
                best=best_token,
                best_score=best_score,
                second_best=second_token,
                second_score=second_score,
                protected=tc.protected,
                candidate_sources=candidate_sources,
            )
            decisions.append(decision)

        return decisions

    def decide_token(
        self,
        *,
        original: str,
        best: str | None,
        best_score: float,
        second_best: str | None = None,
        second_score: float = 0.0,
        protected: bool = False,
        candidate_sources: tuple[CommonCandidateSource, ...] = (),
    ) -> CorrectionDecision:
        if best is None:
            return CorrectionDecision(
                original=original,
                best=None,
                best_score=0.0,
                decision=DecisionType.REJECT,
                reason=DecisionReason.NO_CANDIDATE,
            )

        if protected:
            return CorrectionDecision(
                original=original,
                best=original,
                best_score=best_score,
                second_best=second_best,
                second_score=second_score,
                margin=0.0,
                decision=DecisionType.REJECT,
                reason=DecisionReason.PROTECTED,
            )

        margin = _safe_margin(best_score, second_score)

        if best == original:
            return CorrectionDecision(
                original=original,
                best=original,
                best_score=best_score,
                second_best=second_best,
                second_score=second_score,
                margin=margin,
                decision=DecisionType.REJECT,
                reason=DecisionReason.IDENTITY,
                candidate_sources=candidate_sources,
            )

        if best_score < self._config.replace_threshold:
            return CorrectionDecision(
                original=original,
                best=best,
                best_score=best_score,
                second_best=second_best,
                second_score=second_score,
                margin=margin,
                decision=DecisionType.FLAG,
                reason=DecisionReason.LOW_CONFIDENCE,
                candidate_sources=candidate_sources,
            )

        if margin < self._config.ambiguous_margin:
            return CorrectionDecision(
                original=original,
                best=best,
                best_score=best_score,
                second_best=second_best,
                second_score=second_score,
                margin=margin,
                decision=DecisionType.FLAG,
                reason=DecisionReason.AMBIGUOUS,
                candidate_sources=candidate_sources,
            )

        if margin < self._config.min_margin:
            return CorrectionDecision(
                original=original,
                best=best,
                best_score=best_score,
                second_best=second_best,
                second_score=second_score,
                margin=margin,
                decision=DecisionType.NEED_CONTEXT,
                reason=DecisionReason.NEEDS_CONTEXT,
                candidate_sources=candidate_sources,
            )

        return CorrectionDecision(
            original=original,
            best=best,
            best_score=best_score,
            second_best=second_best,
            second_score=second_score,
            margin=margin,
            decision=DecisionType.ACCEPT,
            reason=DecisionReason.ACCEPTED,
            candidate_sources=candidate_sources,
        )


# -- helpers ----------------------------------------------------------------


def _safe_margin(best_score: float, second_score: float) -> float:
    return round(best_score - second_score, 10)


def _find_second_best_for_position(
    ranked_sequences: list[ScoredSequence],
    position: int,
    best_token: str,
) -> tuple[str | None, float]:
    """Find the best token at *position* that differs from *best_token*.

    Skips sequences whose token at *position* matches *best_token* to
    avoid counting the same correction as its own second-best.
    """
    for scored_seq in ranked_sequences[1:]:
        token = scored_seq.sequence.tokens[position]
        if token != best_token:
            return token, scored_seq.confidence
    return None, 0.0


def _collect_sources(
    token_candidates: object,
) -> tuple[CommonCandidateSource, ...]:
    sources: set[CommonCandidateSource] = set()
    _map: dict[str, CommonCandidateSource] = {
        "original": CommonCandidateSource.SURFACE_INDEX,
        "ocr_confusion": CommonCandidateSource.OCR_CONFUSION_INDEX,
        "syllable_map": CommonCandidateSource.NO_TONE_INDEX,
        "word_lexicon": CommonCandidateSource.SURFACE_INDEX,
        "abbreviation": CommonCandidateSource.ABBREVIATION_INDEX,
        "phrase_specific": CommonCandidateSource.PHRASE_INDEX,
        "domain_specific": CommonCandidateSource.PHRASE_INDEX,
        "edit_distance": CommonCandidateSource.RULE,
    }
    candidates_list: list[object] = list(getattr(token_candidates, "candidates", []))
    for c in candidates_list:
        for s in getattr(c, "sources", []):
            mapped = _map.get(str(s))
            if mapped is not None:
                sources.add(mapped)
    return tuple(sorted(sources, key=str))
