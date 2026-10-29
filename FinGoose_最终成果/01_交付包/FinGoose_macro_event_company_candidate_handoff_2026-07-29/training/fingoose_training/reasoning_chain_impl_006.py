"""Compile empty legacy scopes into explicit open-gate canonical chains."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .reasoning_chain_impl_005 import (
    compile_reasoning_chain as _compile_v5,
    render_chain_summary,
)


INDUSTRY_TYPES = (
    "EVENT_FACT",
    "BEHAVIOR_OR_POLICY_CHANGE",
    "OBSERVABLE_DRIVER",
    "INDUSTRY_OPERATING_VARIABLE",
    "INDUSTRY_REVENUE_OR_COST_VARIABLE",
    "DIRECTION_ASSESSMENT",
    "PRICE_CONFOUNDER_AND_COUNTEREVIDENCE",
)
COMPANY_TYPES = (
    "EVENT_FACT",
    "BEHAVIOR_OR_POLICY_CHANGE",
    "OBSERVABLE_OPERATING_VARIABLE",
    "INDUSTRY_REVENUE_OR_COST_VARIABLE",
    "COMPANY_BUSINESS_EXPOSURE",
    "DIRECTION_ASSESSMENT",
    "PRICE_AND_CONFOUNDER_VERIFICATION",
)


def _placeholder_nodes(prefix: str, node_types: Sequence[str], company: bool) -> list[dict[str, Any]]:
    nodes = []
    for index, node_type in enumerate(node_types, start=1):
        if index == len(node_types):
            statement_class = "CALCULATED_FACT"
        elif index <= 2 or (company and node_type == "COMPANY_BUSINESS_EXPOSURE"):
            statement_class = "SOURCE_FACT"
        else:
            statement_class = "RESEARCH_INFERENCE"
        nodes.append(
            {
                "node_id": f"{prefix}-gap-{index}",
                "node_type": node_type,
                "statement_class": statement_class,
                "statement_zh": f"{node_type} 待补充，不得形成确定性结论。",
                "premise_node_ids": [f"{prefix}-gap-{index - 1}"] if index > 1 else [],
            }
        )
    return nodes


def compile_reasoning_chain(
    task_type: str,
    *,
    scope: Mapping[str, Any],
    evidence_registry: Sequence[Mapping[str, Any]],
    parent_chain_refs: Sequence[str] = (),
) -> dict[str, Any]:
    prepared = deepcopy(dict(scope))
    mechanism = prepared.get("mechanism_chain")
    empty_mechanism = isinstance(mechanism, Mapping) and not mechanism.get("nodes")
    if empty_mechanism and task_type in {"INDUSTRY_IMPACT", "COMPANY_IMPACT"}:
        prefix = str(prepared.get("event_industry_mapping_id") or prepared.get("mapping_id") or "scope")
        prepared["nodes"] = _placeholder_nodes(
            prefix,
            INDUSTRY_TYPES if task_type == "INDUSTRY_IMPACT" else COMPANY_TYPES,
            company=task_type == "COMPANY_IMPACT",
        )
        prepared["edges"] = []
        prepared.pop("mechanism_chain", None)
    return _compile_v5(
        task_type,
        scope=prepared,
        evidence_registry=evidence_registry,
        parent_chain_refs=parent_chain_refs,
    )


__all__ = ["compile_reasoning_chain", "render_chain_summary"]
