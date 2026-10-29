"""Infer source-fact semantics for canonical source node types."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .reasoning_chain_impl_007 import (
    compile_reasoning_chain as _compile_v7,
    render_chain_summary,
)


SOURCE_NODE_TYPES = {"EVENT_FACT", "COMPANY_BUSINESS_EXPOSURE"}


def _normalize_source_types(nodes: Any) -> None:
    if not isinstance(nodes, list):
        return
    for node in nodes:
        if (
            isinstance(node, dict)
            and not node.get("statement_class")
            and not node.get("claim_kind")
            and str(node.get("node_type")) in SOURCE_NODE_TYPES
        ):
            node["statement_class"] = "SOURCE_FACT"


def compile_reasoning_chain(
    task_type: str,
    *,
    scope: Mapping[str, Any],
    evidence_registry: Sequence[Mapping[str, Any]],
    parent_chain_refs: Sequence[str] = (),
) -> dict[str, Any]:
    prepared = deepcopy(dict(scope))
    _normalize_source_types(prepared.get("nodes"))
    mechanism = prepared.get("mechanism_chain")
    if isinstance(mechanism, dict):
        _normalize_source_types(mechanism.get("nodes"))
    for graph in prepared.get("transmission_graphs") or []:
        if isinstance(graph, dict):
            _normalize_source_types(graph.get("nodes"))
    return _compile_v7(
        task_type,
        scope=prepared,
        evidence_registry=evidence_registry,
        parent_chain_refs=parent_chain_refs,
    )


__all__ = ["compile_reasoning_chain", "render_chain_summary"]
