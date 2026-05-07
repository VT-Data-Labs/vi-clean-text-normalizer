"""Pipeline-level error types."""


class PipelineError(Exception):
    """Base error for all pipeline failures."""


class PipelineInputTooLargeError(PipelineError):
    """Raised when input exceeds ``max_input_chars``."""


class PipelineDependencyError(PipelineError):
    """Raised when a required dependency cannot be loaded."""


class PipelineExecutionError(PipelineError):
    """Raised when a pipeline stage fails unexpectedly."""
