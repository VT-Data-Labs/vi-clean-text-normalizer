"""M6.5 - Production pipeline orchestration layer.

Wires Stage 1-6 into a single ``correct_text()`` function and
:class:`TextCorrector` class.
"""

from vn_corrector.pipeline.config import PipelineConfig
from vn_corrector.pipeline.corrector import TextCorrector, correct_text
from vn_corrector.pipeline.errors import (
    PipelineDependencyError,
    PipelineError,
    PipelineExecutionError,
    PipelineInputTooLargeError,
)

__all__ = [
    "PipelineConfig",
    "PipelineDependencyError",
    "PipelineError",
    "PipelineExecutionError",
    "PipelineInputTooLargeError",
    "TextCorrector",
    "correct_text",
]
