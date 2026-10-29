"""Compatibility refinement for canonical milestone IDs in content paths."""

from __future__ import annotations

from typing import Any, Mapping

from .research_content import build_event_research_content as _build
from .research_content import select_task_content


def build_event_research_content(ui_event: Mapping[str, Any]) -> dict[str, Any]:
    content = _build(ui_event)
    aliases: dict[str, str] = {}
    for row in ui_event.get("timeline") or []:
        if not isinstance(row, Mapping):
            continue
        fast = str(row.get("fast_node_id") or "")
        canonical = str(row.get("original_milestone_id") or fast)
        if fast and canonical and fast != canonical:
            aliases[fast] = canonical
    if aliases:
        content["main_path_node_ids"] = [
            aliases.get(str(node_id), str(node_id))
            for node_id in content.get("main_path_node_ids") or []
        ]
        content["statement_by_node_id"].update(
            {
                aliases.get(node_id, node_id): statement
                for node_id, statement in content.get("statement_by_node_id", {}).items()
            }
        )
    return content


__all__ = ["build_event_research_content", "select_task_content"]
