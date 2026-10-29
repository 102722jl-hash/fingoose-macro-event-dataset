"""Final builder with hidden-material filtering."""

from __future__ import annotations

from typing import Mapping

from .research_content_impl_003 import build_event_research_content
from .unified_builder_impl_001 import BuildError, build_unified_events as _build_v1, group_by, index_unique
from .unified_builder_impl_003 import _attach_company_chains, _attach_content_to_scopes, _attach_event_chain, _attach_industry_chains, _attach_qa_chains


def build_unified_events(source, dataset_version, *, ui_reference=None):
    records = _build_v1(source, dataset_version)
    if ui_reference is None:
        if len(records) > 1:
            raise BuildError("content alignment requires ui_reference")
        return records
    ui_by_id = {str(row.get("event_id")): row for row in ui_reference.get("events") or [] if isinstance(row, Mapping)}
    for record in records:
        ui_event = ui_by_id.get(str(record["event_id"]))
        if ui_event is None:
            raise BuildError(f"ui reference missing event_id={record['event_id']}")
        content = build_event_research_content(ui_event)
        _attach_content_to_scopes(record, content)
        _attach_event_chain(record, content)
        _attach_industry_chains(record, content)
        _attach_company_chains(record, content)
        _attach_qa_chains(record, content)
    return records


__all__ = ["BuildError", "build_unified_events", "group_by", "index_unique"]
