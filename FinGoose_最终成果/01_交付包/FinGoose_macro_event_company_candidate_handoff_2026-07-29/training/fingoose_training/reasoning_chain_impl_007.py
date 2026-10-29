"""Normalize legacy claim_kind into the canonical statement_class field."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .reasoning_chain_impl_006 import (
    compile_reasoning_chain as _compile_v6,
    render_chain_summary,
)


def _normalize_claim_kind(nodes: Any) -> None:
    if not isinstance(nodes, list):
        return
    for node in nodes:
        if isinstance(node, dict) and not node.get("statement_class") and node.get("claim_kind"):
            node["statement_class"] = node["claim_kind"]


def compile_reasoning_chain(
    task_type: str,
    *,
    scope: Mapping[str, Any],
    evidence_registry: Sequence[Mapping[str, Any]],
    parent_chain_refs: Sequence[str] = (),
) -> dict[str, Any]:
    prepared = deepcopy(dict(scope))
    _normalize_claim_kind(prepared.get("nodes"))
    mechanism = prepared.get("mechanism_chain")
    if isinstance(mechanism, dict):
        _normalize_claim_kind(mechanism.get("nodes"))
    for graph in prepared.get("transmission_graphs") or []:
        if isinstance(graph, dict):
            _normalize_claim_kind(graph.get("nodes"))
    return _compile_v6(
        task_type,
        scope=prepared,
        evidence_registry=evidence_registry,
        parent_chain_refs=parent_chain_refs,
    )


__all__ = ["compile_reasoning_chain", "render_chain_summary"]
