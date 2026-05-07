from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from vn_corrector.common.lexicon import LexiconStoreInterface
from vn_corrector.pipeline.config import PipelineConfig
from vn_corrector.pipeline.errors import PipelineDependencyError
from vn_corrector.stage2_lexicon import load_default_lexicon
from vn_corrector.stage4_candidates import CandidateGenerator, CandidateGeneratorConfig
from vn_corrector.stage5_scorer import PhraseScorer, PhraseScorerConfig
from vn_corrector.stage5_scorer.backends.json_ngram_store import JsonNgramStore
from vn_corrector.stage6_decision import DecisionEngine, DecisionEngineConfig


def _get_ngram_path() -> str:
    root = Path(__file__).resolve().parent.parent.parent.parent
    ngram_file = root / "resources" / "ngrams" / "ngram_store.vi.json"
    return str(ngram_file)


def _build_decision_config(pipeline_config: PipelineConfig) -> DecisionEngineConfig:
    return DecisionEngineConfig(
        replace_threshold=pipeline_config.min_accept_confidence,
        min_margin=pipeline_config.min_margin,
        ambiguous_margin=pipeline_config.min_margin / 2,
    )


def _build_scorer_config(pipeline_config: PipelineConfig) -> PhraseScorerConfig:
    return PhraseScorerConfig(
        max_tokens_per_window=pipeline_config.max_window_size,
        max_candidates_per_token=pipeline_config.max_candidates_per_token,
        min_apply_confidence=pipeline_config.min_accept_confidence,
        min_score_margin=pipeline_config.min_margin,
    )


def _build_candidate_config(pipeline_config: PipelineConfig) -> CandidateGeneratorConfig:
    return CandidateGeneratorConfig(
        max_candidates_per_token=pipeline_config.max_candidates_per_token,
    )


@dataclass
class PipelineContext:
    """Holds all reusable pipeline dependencies.

    Created once by :class:`~vn_corrector.pipeline.corrector.TextCorrector`
    and reused across ``correct()`` calls.
    """

    config: PipelineConfig
    lexicon: LexiconStoreInterface
    candidate_generator: CandidateGenerator
    scorer: PhraseScorer
    decision_engine_config: DecisionEngineConfig
    decision_engine: DecisionEngine


def build_pipeline_context(config: PipelineConfig) -> PipelineContext:
    """Build a :class:`PipelineContext` from a :class:`PipelineConfig`.

    Loads the lexicon, n-gram store, candidate generator, scorer, and
    decision engine.  Raises :class:`PipelineDependencyError` when a
    required resource is missing.
    """
    try:
        lexicon: LexiconStoreInterface = load_default_lexicon("json")
    except Exception as exc:
        raise PipelineDependencyError(f"Failed to load default lexicon: {exc}") from exc

    candidate_generator = CandidateGenerator(
        lexicon=lexicon,
        config=_build_candidate_config(config),
    )

    try:
        ngram_store = JsonNgramStore(_get_ngram_path())
    except Exception as exc:
        raise PipelineDependencyError(f"Failed to load n-gram store: {exc}") from exc

    scorer = PhraseScorer(
        ngram_store=ngram_store,
        lexicon=lexicon,
        config=_build_scorer_config(config),
    )

    decision_config = _build_decision_config(config)
    decision_engine = DecisionEngine(config=decision_config)

    return PipelineContext(
        config=config,
        lexicon=lexicon,
        candidate_generator=candidate_generator,
        scorer=scorer,
        decision_engine_config=decision_config,
        decision_engine=decision_engine,
    )
