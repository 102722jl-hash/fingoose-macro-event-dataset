"""Filter hidden UI-only material and constrain answer evidence to auditable records."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .research_content_impl_002 import build_event_research_content as _build
from .research_content import select_task_content


def _public(value: Any) -> Any:
    if isinstance(value, Mapping):
        visibility = str(value.get("visibility") or value.get("availability_scope") or "").upper()
        if "HIDDEN" in visibility or "EVALUATOR_ONLY" in visibility:
            return None
        result = {}
        for key, child in value.items():
            clean = _public(child)
            if clean is not None:
                result[key] = clean
        return result
    if isinstance(value, list):
        return [clean for item in value if (clean := _public(item)) is not None]
    return deepcopy(value)


def build_event_research_content(ui_event: Mapping[str, Any]) -> dict[str, Any]:
    content = _public(_build(ui_event))
    registry = [
        row for row in content.get("evidence_registry") or []
        if any(row.get(key) for key in ("original_quote", "locator", "source_url", "publisher", "title"))
    ]
    content["evidence_registry"] = registry
    registry_ids = {str(row["evidence_id"]) for row in registry if row.get("evidence_id")}
    content["answer_evidence_ids"] = sorted(registry_ids)
    content["primary_answer_evidence_ids"] = [
        evidence_id for evidence_id in content.get("primary_answer_evidence_ids") or []
        if evidence_id in registry_ids
    ]
    return content


__all__ = ["build_event_research_content", "select_task_content"]
