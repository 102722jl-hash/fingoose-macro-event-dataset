"""Final projector using clean task-specific answer rendering."""

from .sft_projector_impl_008 import project_sft_samples as _project

# The public implementation is selected by the renderer import in the package loader.
project_sft_samples = _project

__all__ = ["project_sft_samples"]
