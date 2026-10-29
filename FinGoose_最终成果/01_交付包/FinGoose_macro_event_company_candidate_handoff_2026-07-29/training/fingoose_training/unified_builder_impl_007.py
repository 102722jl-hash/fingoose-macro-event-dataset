"""Content alignment with legacy single-event builder compatibility."""

from __future__ import annotations

from .unified_builder_impl_002 import build_unified_events as _build_legacy
from .unified_builder_impl_006 import BuildError, build_unified_events as _build_aligned, group_by, index_unique


def build_unified_events(source, dataset_version, *, ui_reference=None):
    if ui_reference is None:
        event_ids = {str(row.get("event_id")) for row in source.get("event_episodes") or [] if row.get("event_id")}
        if len(event_ids) > 1:
            raise BuildError("content alignment requires ui_reference")
        return _build_legacy(source, dataset_version)
    return _build_aligned(source, dataset_version, ui_reference=ui_reference)


__all__ = ["BuildError", "build_unified_events", "group_by", "index_unique"]
