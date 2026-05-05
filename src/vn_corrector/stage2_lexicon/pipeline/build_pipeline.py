"""Lexicon build pipeline — orchestrates the full build, validation, and export.

Usage::

    from vn_corrector.stage2_lexicon.builders import (
        SyllableBuilder, WordBuilder, PhraseBuilder,
        ConfusionBuilder, AbbreviationBuilder,
    )
    from vn_corrector.stage2_lexicon.pipeline import build_all

    result = build_all(
        syllable_data=[...],
        word_data=[...],
        phrase_data=[...],
        confusion_data=[...],
        abbreviation_data=[...],
        version="2026-05-06",
        source_name="corpus_v1",
    )

    print(result.stats.total_entries)   # e.g. 4812
    print(result.metadata.version)      # "2026-05-06"
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from vn_corrector.common.types import (
    AbbreviationEntry,
    LexiconEntry,
    LexiconRecord,
    LexiconSource,
    OcrConfusionEntry,
    PhraseEntry,
    Provenance,
)
from vn_corrector.stage2_lexicon.builders import (
    AbbreviationBuilder,
    ConfusionBuilder,
    LexiconBuilder,
    PhraseBuilder,
    SyllableBuilder,
    WordBuilder,
)
from vn_corrector.stage2_lexicon.core.types import (
    BuildConfig,
    BuilderInput,
    BuilderOutput,
    LexiconBuildStats,
    LexiconMetadata,
)

# ---------------------------------------------------------------------------
# Pipeline result
# ---------------------------------------------------------------------------


@dataclass
class PipelineResult:
    """Full result of a :func:`build_all` run."""

    entries: list[LexiconEntry]
    metadata: LexiconMetadata
    stats: LexiconBuildStats
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    export_paths: dict[str, str] = field(default_factory=dict)
    provenance: Provenance | None = None


# ---------------------------------------------------------------------------
# Pipeline class
# ---------------------------------------------------------------------------


@dataclass
class BuildPipeline:
    """Orchestrates a full lexicon build.

    Parameters
    ----------
    syllable_builder:
        Builder for syllable entries.  Defaults to :class:`SyllableBuilder`.
    word_builder:
        Builder for word entries.  Defaults to :class:`WordBuilder`.
    phrase_builder:
        Builder for phrase entries.  Defaults to :class:`PhraseBuilder`.
    confusion_builder:
        Builder for OCR confusion entries.  Defaults to :class:`ConfusionBuilder`.
    abbreviation_builder:
        Builder for abbreviation entries.  Defaults to :class:`AbbreviationBuilder`.
    """

    syllable_builder: LexiconBuilder[LexiconEntry] = field(default_factory=SyllableBuilder)
    word_builder: LexiconBuilder[LexiconEntry] = field(default_factory=WordBuilder)
    phrase_builder: LexiconBuilder[PhraseEntry] = field(default_factory=PhraseBuilder)
    confusion_builder: LexiconBuilder[OcrConfusionEntry] = field(default_factory=ConfusionBuilder)
    abbreviation_builder: LexiconBuilder[AbbreviationEntry] = field(
        default_factory=AbbreviationBuilder
    )

    def run(
        self,
        syllable_data: list[dict[str, Any]] | None = None,
        word_data: list[dict[str, Any]] | None = None,
        phrase_data: list[dict[str, Any]] | None = None,
        confusion_data: list[dict[str, Any]] | None = None,
        abbreviation_data: list[dict[str, Any]] | None = None,
        *,
        version: str | None = None,
        source_name: str = "built-in",
        config: BuildConfig | None = None,
        output_dir: str | None = None,
    ) -> PipelineResult:
        """Run the full build pipeline.

        Parameters
        ----------
        syllable_data:
            Raw data for syllable builder (list of dicts with base/forms).
        word_data:
            Raw data for word builder (list of dicts with surface/type/freq).
        phrase_data:
            Raw data for phrase builder (list of dicts with phrase/n).
        confusion_data:
            Raw data for confusion builder (list of dicts with noisy/corrections).
        abbreviation_data:
            Raw data for abbreviation builder (list of dicts with abbreviation/expansions).
        version:
            Version string (defaults to today's date).
        source_name:
            Human-readable source description.
        config:
            Full :class:`BuildConfig` for advanced settings.
        output_dir:
            Directory to write exported files.  Falls back to ``config.output_dir``.

        Returns
        -------
        PipelineResult
            Full build result including entries, stats, and export paths.
        """
        version = version or date.today().isoformat()
        source = LexiconSource.CORPUS if source_name != "built-in" else LexiconSource.BUILT_IN
        provenance = Provenance(source=source, source_name=source_name, version=version)

        all_entries: list[Any] = []
        errors: list[str] = []
        warnings: list[str] = []

        # -- Run each builder ----------------------------------------------
        builder_steps: list[tuple[str, LexiconBuilder[Any], Any]] = [
            ("syllables", self.syllable_builder, syllable_data),
            ("words", self.word_builder, word_data),
            ("phrases", self.phrase_builder, phrase_data),
            ("confusions", self.confusion_builder, confusion_data),
            ("abbreviations", self.abbreviation_builder, abbreviation_data),
        ]

        for name, builder, data in builder_steps:
            if not data:
                warnings.append(f"No data provided for '{name}' builder — skipping")
                continue

            try:
                builder_input = BuilderInput(
                    name=name,
                    data=data,
                    source=source,
                    version=version,
                )
                output: BuilderOutput[Any] = builder.build(builder_input)
                entries = list(output.entries)

                # Validate
                if config is None or config.validate:
                    validation_errors = self._validate_builder_output(name, builder, entries)
                    errors.extend(validation_errors)

                all_entries.extend(entries)
            except (TypeError, ValueError, RuntimeError) as exc:
                errors.append(f"Builder '{name}' failed: {exc}")

        # -- Compute stats ------------------------------------------------
        stats = self._compute_stats(all_entries)

        # -- Build metadata -----------------------------------------------
        metadata = LexiconMetadata(
            version=version,
            source=source_name,
            builder="BuildPipeline",
            stats=stats,
            provenance=provenance,
        )

        # -- Export -------------------------------------------------------
        export_paths: dict[str, str] = {}
        out_dir = output_dir or (config.output_dir if config else "resources/lexicons")

        if config is None or "json" in config.exporters:
            json_path = self._export_json(all_entries, metadata, out_dir)
            if json_path:
                export_paths["json"] = json_path

        if config is not None and "sqlite" in config.exporters:
            sqlite_path = self._export_sqlite(all_entries, out_dir, version)
            if sqlite_path:
                export_paths["sqlite"] = sqlite_path

        return PipelineResult(
            entries=all_entries,
            metadata=metadata,
            stats=stats,
            errors=errors,
            warnings=warnings,
            export_paths=export_paths,
            provenance=provenance,
        )

    # -- Internal helpers --------------------------------------------------

    @staticmethod
    def _validate_builder_output(
        name: str,
        builder: LexiconBuilder[Any],
        entries: list[LexiconRecord],
    ) -> list[str]:
        """Validate builder output and return error messages."""
        errors: list[str] = []
        validation_errors = builder.validate_output(entries)
        for err in validation_errors:
            errors.append(f"[{name}] {err}")
        return errors

    @staticmethod
    def _compute_stats(entries: list[Any]) -> LexiconBuildStats:
        """Compute aggregate statistics from built entries.

        Handles mixed entry types: :class:`LexiconEntry`, :class:`PhraseEntry`,
        :class:`OcrConfusionEntry`, :class:`AbbreviationEntry`.
        """
        by_kind: dict[str, int] = {}
        domain_coverage: dict[str, int] = {}
        surfaces: set[str] = set()
        normalized_keys: set[str] = set()

        for e in entries:
            if hasattr(e, "kind"):
                kind_str = str(e.kind.value)
                by_kind[kind_str] = by_kind.get(kind_str, 0) + 1
            elif isinstance(e, PhraseEntry):
                by_kind["phrase"] = by_kind.get("phrase", 0) + 1
            elif isinstance(e, OcrConfusionEntry):
                by_kind["ocr_confusion"] = by_kind.get("ocr_confusion", 0) + 1
            elif isinstance(e, AbbreviationEntry):
                by_kind["abbreviation"] = by_kind.get("abbreviation", 0) + 1

            surfaces.add(getattr(e, "surface", getattr(e, "phrase", getattr(e, "noisy", ""))))
            no_tone = getattr(e, "no_tone", getattr(e, "normalized_noisy", ""))
            if no_tone:
                normalized_keys.add(no_tone)
            domain = getattr(e, "domain", None)
            if domain:
                domain_coverage[domain] = domain_coverage.get(domain, 0) + 1

        return LexiconBuildStats(
            total_entries=len(entries),
            total_surfaces=len(surfaces),
            total_unique_normalized=len(normalized_keys),
            by_kind=by_kind,
            domain_coverage=domain_coverage,
        )

    @staticmethod
    def _export_json(
        entries: list[LexiconRecord],
        metadata: LexiconMetadata,
        output_dir: str,
    ) -> str | None:
        """Export entries as a JSON package with metadata.

        Handles mixed entry types: :class:`LexiconEntry`, :class:`PhraseEntry`,
        :class:`OcrConfusionEntry`, :class:`AbbreviationEntry`.
        """
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)

        serialised: list[dict[str, object]] = []
        for e in entries:
            record: dict[str, object] = {
                "entry_id": e.entry_id,
                "type": type(e).__name__,
            }
            # Common fields
            for attr in ("surface", "phrase", "noisy"):
                if hasattr(e, attr):
                    record["surface"] = getattr(e, attr)
                    break
            for attr in ("normalized", "no_tone"):
                if hasattr(e, attr):
                    record[attr] = getattr(e, attr)
            if hasattr(e, "kind"):
                record["kind"] = str(e.kind.value)
            if hasattr(e, "score"):
                record["score"] = {
                    "confidence": e.score.confidence,
                    "frequency": e.score.frequency,
                }
            if hasattr(e, "domain") and e.domain:
                record["domain"] = e.domain
            if hasattr(e, "tags"):
                record["tags"] = list(e.tags)
            serialised.append(record)

        package = {
            "metadata": metadata.to_dict(),
            "entries": serialised,
        }

        file_path = path / "lexicon_package.json"
        with file_path.open("w", encoding="utf-8") as f:
            json.dump(package, f, ensure_ascii=False, indent=2)

        return str(file_path)

    @staticmethod
    def _export_sqlite(
        _entries: list[LexiconEntry],
        _output_dir: str,
        _version: str = "",
    ) -> None:
        """Reserved for SQLite export (delegated to SqliteLexiconStore)."""


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def _default_empty_data() -> dict[str, list[dict[str, Any]]]:
    """Return an empty data dict so callers don't need to pass empty lists."""
    return {}


def build_all(  # pylint: disable=too-many-arguments
    syllable_data: list[dict[str, Any]] | None = None,
    word_data: list[dict[str, Any]] | None = None,
    phrase_data: list[dict[str, Any]] | None = None,
    confusion_data: list[dict[str, Any]] | None = None,
    abbreviation_data: list[dict[str, Any]] | None = None,
    *,
    version: str | None = None,
    source_name: str = "built-in",
    config: BuildConfig | None = None,
    output_dir: str | None = None,
) -> PipelineResult:
    """Convenience function to run the full build pipeline.

    Usage::

        from vn_corrector.stage2_lexicon.pipeline import build_all

        result = build_all(
            syllable_data=my_syllable_list,
            word_data=my_word_list,
            version="2026-05-06",
        )

    See :meth:`BuildPipeline.run` for parameter documentation.
    """
    pipeline = BuildPipeline()
    return pipeline.run(
        syllable_data=syllable_data,
        word_data=word_data,
        phrase_data=phrase_data,
        confusion_data=confusion_data,
        abbreviation_data=abbreviation_data,
        version=version,
        source_name=source_name,
        config=config,
        output_dir=output_dir,
    )
