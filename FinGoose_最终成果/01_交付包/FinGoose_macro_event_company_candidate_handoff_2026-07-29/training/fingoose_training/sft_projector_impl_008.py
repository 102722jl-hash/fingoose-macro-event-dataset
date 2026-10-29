"""Content-aligned projection with legacy-record compatibility."""

from __future__ import annotations

from .sft_projector_impl_003 import project_sft_samples as _project_legacy
from .sft_projector_impl_007 import project_sft_samples as _project_aligned


def project_sft_samples(unified_events, enabled_tasks=None):
    if any(not isinstance(event.get("research_content"), dict) for event in unified_events):
        return _project_legacy(unified_events, enabled_tasks)
    return _project_aligned(unified_events, enabled_tasks)


__all__ = ["project_sft_samples"]
