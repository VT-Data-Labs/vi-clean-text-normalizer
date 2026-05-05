"""Stage-2 build pipeline.

Orchestrates the full lexicon build: runs all builders, validates outputs,
collects statistics, attaches versioning metadata, and exports to the
desired backends (JSON, SQLite).
"""

from vn_corrector.stage2_lexicon.pipeline.build_pipeline import BuildPipeline, build_all

__all__ = [
    "BuildPipeline",
    "build_all",
]
