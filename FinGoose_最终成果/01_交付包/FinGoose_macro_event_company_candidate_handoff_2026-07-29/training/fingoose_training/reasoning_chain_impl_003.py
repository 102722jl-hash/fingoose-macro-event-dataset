"""Compatibility fixes for empty legacy chains."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .reasoning_chain_impl_002 import (
    compile_reasoning_chain as _compile_v2,
    render_chain_summary,
)


def compile_reasoning_chain(
    task_type: str,
    *,
    scope: Mapping[str, Any],
    evidence_registry: Sequence[Mapping[str, Any]],
    parent_chain_refs: Sequence[str] = (),
) -> dict[str, Any]:
    prepared = deepcopy(dict(scope))
    mechanism = prepared.get("mechanism_chain")
    if task_type in {"INDUSTRY_IMPACT", "COMPANY_IMPACT"} and isinstance(mechanism, Mapping) and not mechanism.get("nodes"):
        prepared["nodes"] = [
            {
                "node_id": f"{prepared.get('event_industry_mapping_id') or prepared.get('mapping_id') or 'scope'}-boundary",
                "node_type": "DIRECTION_ASSESSMENT",
                "statement_class": "RESEARCH_INFERENCE",
                "statement_zh": "机制链尚未提供完整节点，保持候选边界。",
            }
        ]
        prepared.pop("mechanism_chain", None)
    return _compile_v2(
        task_type,
        scope=prepared,
        evidence_registry=evidence_registry,
        parent_chain_refs=parent_chain_refs,
    )


__all__ = ["compile_reasoning_chain", "render_chain_summary"]
