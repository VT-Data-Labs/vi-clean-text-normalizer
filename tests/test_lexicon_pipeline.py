"""Tests for the Stage-2 lexicon build pipeline."""

from pathlib import Path

from vn_corrector.stage2_lexicon.builders import SyllableBuilder
from vn_corrector.stage2_lexicon.pipeline import BuildPipeline, build_all


class TestBuildPipeline:
    def test_empty_pipeline(self):
        pipeline = BuildPipeline()
        result = pipeline.run()
        assert result.stats.total_entries == 0
        assert len(result.errors) == 0
        assert result.metadata.version is not None

    def test_syllable_only(self):
        pipeline = BuildPipeline()
        result = pipeline.run(
            syllable_data=[{"base": "muong", "forms": ["muỗng", "mường"]}],
            version="2026-05-06",
        )
        assert result.stats.total_entries == 2
        assert result.stats.by_kind["syllable"] == 2
        assert result.stats.total_surfaces == 2
        assert result.stats.total_unique_normalized == 1

    def test_all_builders(self):
        result = build_all(
            syllable_data=[
                {"base": "muong", "forms": ["muỗng", "mường"]},
            ],
            word_data=[
                {"surface": "số muỗng", "type": "common_word", "freq": 0.9},
            ],
            phrase_data=[
                {"phrase": "số muỗng gạt ngang", "n": 3, "freq": 0.95},
            ],
            confusion_data=[
                {"noisy": "mùông", "corrections": ["muỗng"]},
            ],
            abbreviation_data=[
                {"abbreviation": "2pn", "expansions": ["2 phòng ngủ"]},
            ],
            version="2026-05-06",
        )
        # 2 syllables + 1 word + 1 phrase + 1 confusion + 1 abbreviation = 6
        assert result.stats.total_entries == 6
        assert result.metadata.version == "2026-05-06"
        assert len(result.errors) == 0

    def test_build_with_none_data_skips(self):
        result = build_all(
            syllable_data=[{"base": "test", "forms": ["test"]}],
            version="test",
        )
        assert result.stats.total_entries == 1
        # Word, phrase, confusion, abbreviation were all None — warnings emitted
        assert len(result.warnings) >= 1

    def test_pipeline_version_defaults(self):
        result = BuildPipeline().run(
            syllable_data=[{"base": "test", "forms": ["test"]}],
        )
        # Version defaults to today's date — just check it's non-empty
        assert result.metadata.version

    def test_export_json(self, tmp_path: Path) -> None:
        """Verify JSON export creates a file."""
        pipeline = BuildPipeline()
        result = pipeline.run(
            syllable_data=[{"base": "muong", "forms": ["muỗng"]}],
            version="test-export",
            output_dir=str(tmp_path),
        )
        assert "json" in result.export_paths
        json_path = Path(result.export_paths["json"])
        assert json_path.exists()
        assert json_path.stat().st_size > 0

    def test_export_json_contents(self, tmp_path: Path) -> None:
        import json

        result = build_all(
            syllable_data=[{"base": "muong", "forms": ["muỗng"]}],
            version="test-export",
            output_dir=str(tmp_path),
        )
        json_path = Path(result.export_paths["json"])
        with json_path.open(encoding="utf-8") as f:
            data = json.load(f)

        assert "metadata" in data
        assert data["metadata"]["version"] == "test-export"
        assert "entries" in data
        assert len(data["entries"]) == 1
        assert data["entries"][0]["surface"] == "muỗng"

    def test_stats_by_kind(self):
        result = build_all(
            syllable_data=[{"base": "muong", "forms": ["muỗng"]}],
            word_data=[{"surface": "test", "type": "common_word"}],
            version="test",
        )
        assert result.stats.by_kind["syllable"] == 1
        assert result.stats.by_kind["word"] == 1

    def test_stats_domain_coverage(self):
        result = build_all(
            word_data=[
                {"surface": "DHA", "type": "chemical", "domain": "milk_formula"},
                {"surface": "ARA", "type": "chemical", "domain": "milk_formula"},
            ],
            version="test",
        )
        assert result.stats.domain_coverage.get("milk_formula", 0) == 2

    def test_builder_error_handling(self):
        """Pipeline should collect builder errors without crashing."""
        pipeline = BuildPipeline(syllable_builder=SyllableBuilder())
        # Pass invalid data type to trigger TypeError in builder
        result = pipeline.run(
            syllable_data="invalid",  # type: ignore[arg-type]
            version="test",
        )
        assert len(result.errors) >= 1
        assert "syllables" in result.errors[0]

    def test_provenance_in_metadata(self):
        result = build_all(
            syllable_data=[{"base": "test", "forms": ["test"]}],
            version="1.0",
            source_name="test_corpus",
        )
        assert result.provenance is not None
        assert result.provenance.source_name == "test_corpus"
        assert result.provenance.version == "1.0"
