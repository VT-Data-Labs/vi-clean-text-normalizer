"""Candidate generator — orchestrates source generators, merging, ranking, and limits.

This is the main entry point for Stage 4 candidate generation.
"""

from __future__ import annotations

from collections.abc import Sequence

from vn_corrector.common.types import Token, TokenType
from vn_corrector.stage1_normalize import normalize_text, to_no_tone_key
from vn_corrector.stage4_candidates.cache import TokenCache
from vn_corrector.stage4_candidates.config import CandidateGeneratorConfig
from vn_corrector.stage4_candidates.limits import (
    trim_candidate_list,
)
from vn_corrector.stage4_candidates.ranking import rank_candidates
from vn_corrector.stage4_candidates.sources import CandidateSourceGenerator
from vn_corrector.stage4_candidates.sources.abbreviation import AbbreviationSource
from vn_corrector.stage4_candidates.sources.base import IdentitySource
from vn_corrector.stage4_candidates.sources.domain_specific import DomainSpecificSource
from vn_corrector.stage4_candidates.sources.edit_distance import EditDistanceSource
from vn_corrector.stage4_candidates.sources.ocr_confusion import OcrConfusionSource
from vn_corrector.stage4_candidates.sources.phrase_evidence import PhraseEvidenceSource
from vn_corrector.stage4_candidates.sources.syllable_map import SyllableMapSource
from vn_corrector.stage4_candidates.sources.word_lexicon import WordLexiconSource
from vn_corrector.stage4_candidates.types import (
    Candidate,
    CandidateContext,
    CandidateDocument,
    CandidateEvidence,
    CandidateGenerationStats,
    CandidateProposal,
    CandidateRequest,
    CandidateSource,
    LexiconStoreProtocol,
    TokenCandidates,
)


class CandidateGenerator:
    """Deterministic, bounded, explainable candidate generator.

    Orchestrates multiple :class:`CandidateSourceGenerator` instances,
    merges proposals by text, ranks deterministically, and enforces limits.

    Args:
        lexicon: A :class:`~vn_corrector.stage2_lexicon.LexiconStore` instance.
        config: Generator configuration. Uses defaults if ``None``.
        domain: Optional domain name for domain-specific candidate sourcing.
    """

    def __init__(
        self,
        lexicon: LexiconStoreProtocol,
        config: CandidateGeneratorConfig | None = None,
        domain: str | None = None,
    ) -> None:
        self._lexicon = lexicon
        self._config = config or CandidateGeneratorConfig()
        self._domain = domain
        self._cache = TokenCache() if self._config.cache_enabled else None

        # Build source registry
        self._sources: list[CandidateSourceGenerator] = []
        self._register_sources()

    def _register_sources(self) -> None:
        """Register enabled source generators."""
        cfg = self._config

        if cfg.enable_original:
            self._sources.append(IdentitySource())
        if cfg.enable_ocr_confusion:
            self._sources.append(OcrConfusionSource())
        if cfg.enable_syllable_map:
            self._sources.append(SyllableMapSource())
        if cfg.enable_word_lexicon:
            self._sources.append(WordLexiconSource())
        if cfg.enable_abbreviation:
            self._sources.append(AbbreviationSource())
        if cfg.enable_phrase_evidence:
            self._sources.append(PhraseEvidenceSource())
        if cfg.enable_domain_specific:
            self._sources.append(DomainSpecificSource(domain=self._domain))
        if cfg.enable_edit_distance:
            self._sources.append(EditDistanceSource())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_token(
        self,
        token_text: str,
        protected: bool = False,
    ) -> list[Candidate]:
        if self._cache is not None:
            cached = self._cache.get(token_text, "", protected, self._config)
            if cached is not None:
                return cached

        request = CandidateRequest(
            token_text=token_text,
            protected=protected,
        )
        context = CandidateContext(
            tokens=None,
            lexicon=self._lexicon,
            config=self._config,
        )

        candidates = self._generate_for_request(request, context)

        if self._cache is not None:
            self._cache.put(token_text, "", protected, self._config, candidates)

        return candidates

    def generate_for_token_index(
        self,
        tokens: Sequence[Token],
        index: int,
        protected_spans: Sequence[object] | None = None,
    ) -> TokenCandidates:
        if index < 0 or index >= len(tokens):
            raise IndexError(f"Token index {index} out of range (len={len(tokens)})")

        token = tokens[index]
        is_protected = self._is_protected_token(token, protected_spans)
        token_type = token.token_type

        # Determine if this token type should generate full candidates
        identity_only = self._is_identity_only(token_type, is_protected)

        diagnostics: list[str] = []
        if self._config.enable_diagnostics:
            diagnostics.append(
                f"token_type={token_type} protected={is_protected} identity_only={identity_only}"
            )

        if identity_only:
            candidates = self._make_identity_candidates(token.text)
            if self._config.enable_diagnostics:
                diagnostics.append("identity_only: returning original only")
        else:
            request = CandidateRequest(
                token_text=token.text,
                token_index=index,
                token_type=token_type,
                protected=is_protected,
            )
            context = CandidateContext(
                tokens=tokens,
                lexicon=self._lexicon,
                config=self._config,
            )
            candidates = self._generate_for_request(request, context)

        return TokenCandidates(
            token_text=token.text,
            token_index=index,
            protected=is_protected,
            candidates=candidates,
            diagnostics=diagnostics,
        )

    def generate_document(
        self,
        tokens: Sequence[Token],
        protected_spans: Sequence[object] | None = None,
    ) -> CandidateDocument:
        token_candidates: list[TokenCandidates] = []
        stats = CandidateGenerationStats()

        for i in range(len(tokens)):
            tc = self.generate_for_token_index(tokens, i, protected_spans)
            token_candidates.append(tc)
            stats.total_tokens += 1
            if tc.protected:
                stats.protected_tokens += 1
            if len(tc.candidates) == 1 and tc.candidates[0].is_original:
                stats.skipped_tokens += 1
            else:
                stats.generated_tokens += 1
            stats.total_candidates += len(tc.candidates)
            stats.max_candidates_seen = max(stats.max_candidates_seen, len(tc.candidates))

        if stats.total_tokens > 0:
            stats.avg_candidates_per_token = stats.total_candidates / stats.total_tokens
        if self._cache is not None:
            stats.cache_hits = self._cache.hits

        return CandidateDocument(
            token_candidates=token_candidates,
            stats=stats,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _generate_for_request(
        self,
        request: CandidateRequest,
        context: CandidateContext,
    ) -> list[Candidate]:
        """Run all source generators, merge proposals, rank, and trim."""
        if request.protected:
            return self._make_protected_candidates(request.token_text)

        # Collect proposals from all enabled sources
        proposals: list[CandidateProposal] = []
        for source in self._sources:
            try:
                for proposal in source.generate(request, context):
                    proposals.append(proposal)
            except Exception:
                if self._config.enable_diagnostics:
                    import traceback

                    traceback.print_exc()

        # Merge proposals by text into Candidate objects
        candidate_map: dict[str, Candidate] = {}

        for prop in proposals:
            text = prop.text
            if text not in candidate_map:
                candidate_map[text] = Candidate(
                    text=text,
                    normalized=normalize_text(text),
                    no_tone_key=to_no_tone_key(text),
                    sources=set(),
                    evidence=[],
                    prior_score=0.0,
                    is_original=(text == request.token_text),
                )

            cand = candidate_map[text]
            cand.sources.add(prop.source)
            cand.evidence.append(prop.evidence)
            cand.prior_score = max(cand.prior_score, prop.prior_score)

            if prop.edit_distance is not None and (
                cand.edit_distance is None or prop.edit_distance < cand.edit_distance
            ):
                cand.edit_distance = prop.edit_distance

        candidates = list(candidate_map.values())

        # Rank deterministically
        candidates = rank_candidates(
            candidates,
            self._config.source_prior_weights,
            keep_original_first=self._config.keep_original_first,
        )

        # Enforce limit
        if len(candidates) > self._config.max_candidates_per_token:
            candidates = trim_candidate_list(
                candidates,
                self._config.max_candidates_per_token,
                self._config.source_prior_weights,
                keep_original=self._config.keep_original_first,
            )

        return candidates

    def _make_identity_candidates(self, text: str) -> list[Candidate]:
        """Create a single identity candidate (for identity-only tokens)."""
        return [
            Candidate(
                text=text,
                normalized=normalize_text(text),
                no_tone_key=to_no_tone_key(text),
                sources={CandidateSource.ORIGINAL},
                evidence=[
                    CandidateEvidence(
                        source=CandidateSource.ORIGINAL,
                        detail="identity_candidate",
                    )
                ],
                prior_score=self._config.source_prior_weights.get(
                    str(CandidateSource.ORIGINAL), 0.10
                ),
                is_original=True,
            )
        ]

    def _make_protected_candidates(self, text: str) -> list[Candidate]:
        """Create a single identity candidate for a protected token."""
        return [
            Candidate(
                text=text,
                normalized=normalize_text(text),
                no_tone_key=to_no_tone_key(text),
                sources={CandidateSource.ORIGINAL},
                evidence=[
                    CandidateEvidence(
                        source=CandidateSource.ORIGINAL,
                        detail="protected_token_bypass",
                    )
                ],
                prior_score=self._config.source_prior_weights.get(
                    str(CandidateSource.ORIGINAL), 0.10
                ),
                is_original=True,
            )
        ]

    def _is_protected_token(
        self,
        token: Token,
        protected_spans: Sequence[object] | None = None,
    ) -> bool:
        """Check if *token* is protected by M3 or the lexicon."""
        if token.protected:
            return True

        if token.token_type in (TokenType.NUMBER, TokenType.UNIT):
            return True

        if protected_spans is not None:
            token_start = token.span.start
            token_end = token.span.end
            for span in protected_spans:
                span_start = getattr(span, "start", getattr(span, "span_start", 0))
                span_end = getattr(span, "end", getattr(span, "span_end", 0))
                if token_start >= span_start and token_end <= span_end:
                    return True

        return False

    def _is_identity_only(
        self,
        token_type: TokenType,
        protected: bool,
    ) -> bool:
        """Determine if a token type should produce only identity candidates."""
        if protected:
            return True
        if not self._config.skip_non_word_tokens:
            return False
        return str(token_type) in self._config.identity_token_types


__all__ = ["CandidateGenerator"]
