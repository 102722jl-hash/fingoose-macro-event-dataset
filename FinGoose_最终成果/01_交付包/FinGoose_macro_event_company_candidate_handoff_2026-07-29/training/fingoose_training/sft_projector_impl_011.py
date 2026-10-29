"""Clean content projection with legacy compatibility."""

from .sft_projector_impl_003 import project_sft_samples as _legacy
from .sft_projector_impl_010 import project_sft_samples as _aligned


def project_sft_samples(unified_events, enabled_tasks=None):
    if any(not isinstance(event.get("research_content"), dict) for event in unified_events):
        return _legacy(unified_events, enabled_tasks)
    return _aligned(unified_events, enabled_tasks)


__all__ = ["project_sft_samples"]
