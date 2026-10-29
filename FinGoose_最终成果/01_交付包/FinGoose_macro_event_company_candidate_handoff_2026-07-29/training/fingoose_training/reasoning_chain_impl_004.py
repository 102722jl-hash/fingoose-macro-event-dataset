"""Exclude evaluator-only and hidden validation nodes at the compile boundary."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .reasoning_chain_impl_003 import (
    compile_reasoning_chain as _compile_v3,
    render_chain_summary,
)


def _is_hidden_node(node: Mapping[str, Any]) -> bool:
    values = (
        node.get("visibility"),
        node.get("availability_scope"),
        node.get("release_tier"),
    )
    return any(
        isinstance(value, str)
        and ("HIDDEN" in value.upper() or "EVALUATOR_ONLY" in value.upper())
        for value in values
    )


def _filter_graph(graph: dict[str, Any]) -> None:
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        return
    hidden_ids = {
        str(node.get("node_id"))
        for node in nodes
        if isinstance(node, Mapping) and _is_hidden_node(node)
    }
    graph["nodes"] = [
        node
        for node in nodes
        if not (isinstance(node, Mapping) and str(node.get("node_id")) in hidden_ids)
    ]
    if isinstance(graph.get("edges"), list):
        graph["edges"] = [
            edge
            for edge in graph["edges"]
            if isinstance(edge, Mapping)
            and str(edge.get("from_node_id")) not in hidden_ids
            and str(edge.get("to_node_id")) not in hidden_ids
        ]


def compile_reasoning_chain(
    task_type: str,
    *,
    scope: Mapping[str, Any],
    evidence_registry: Sequence[Mapping[str, Any]],
    parent_chain_refs: Sequence[str] = (),
) -> dict[str, Any]:
    prepared = deepcopy(dict(scope))
    _filter_graph(prepared)
    mechanism = prepared.get("mechanism_chain")
    if isinstance(mechanism, dict):
        _filter_graph(mechanism)
    for graph in prepared.get("transmission_graphs") or []:
        if isinstance(graph, dict):
            _filter_graph(graph)
    return _compile_v3(
        task_type,
        scope=prepared,
        evidence_registry=evidence_registry,
        parent_chain_refs=parent_chain_refs,
    )


__all__ = ["compile_reasoning_chain", "render_chain_summary"]
