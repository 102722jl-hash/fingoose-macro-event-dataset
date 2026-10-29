"""Content-aware reasoning-chain compiler layered over the audited v1 compiler."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .reasoning_chain_impl_001 import propagate_node_status, validate_chain_graph
from .reasoning_chain_impl_008 import compile_reasoning_chain as _compile_v8, render_chain_summary

PLACEHOLDER_STATEMENTS = {"", "待补充陈述。", "待补充陈述", "UNKNOWN"}


def _apply_content_statements(nodes: list[dict[str, Any]], content: Mapping[str, Any]) -> None:
    statement_by_id = content.get("statement_by_node_id") or {}
    for node in nodes:
        node_id = str(node.get("node_id"))
        current = str(node.get("statement_zh") or "").strip()
        replacement = statement_by_id.get(node_id)
        if current in PLACEHOLDER_STATEMENTS and replacement:
            node["statement_zh"] = str(replacement)
        if str(node.get("statement_zh") or "").strip() in PLACEHOLDER_STATEMENTS:
            node["statement_zh"] = "该推理环节证据不足，保持候选边界，不形成确定性结论。"


def _apply_premises(graph: dict[str, Any]) -> None:
    premises: dict[str, set[str]] = {}
    for edge in graph.get("edges") or []:
        source = str(edge.get("from_node_id"))
        target = str(edge.get("to_node_id"))
        premises.setdefault(target, set()).add(source)
    for node in graph.get("nodes") or []:
        node["premise_node_ids"] = sorted(premises.get(str(node.get("node_id")), set()))


def _prefer_main_path(graph: dict[str, Any], content: Mapping[str, Any]) -> None:
    node_ids = {str(node.get("node_id")) for node in graph.get("nodes") or []}
    preferred = [str(value) for value in content.get("main_path_node_ids") or []]
    preferred = [node_id for node_id in preferred if node_id in node_ids]
    if len(preferred) < 2:
        return
    graph["main_path_node_ids"] = preferred
    graph["final_node_id"] = preferred[-1]
    graph["side_branch_node_ids"] = sorted(node_ids - set(preferred))
    existing_edges = {
        (str(edge.get("from_node_id")), str(edge.get("to_node_id")))
        for edge in graph.get("edges") or []
    }
    for source, target in zip(preferred, preferred[1:]):
        if (source, target) not in existing_edges:
            graph.setdefault("edges", []).append(
                {"from_node_id": source, "to_node_id": target}
            )


def compile_reasoning_chain(
    task_type: str,
    *,
    scope: Mapping[str, Any],
    evidence_registry: Sequence[Mapping[str, Any]],
    parent_chain_refs: Sequence[str] = (),
) -> dict[str, Any]:
    prepared = deepcopy(dict(scope))
    content = prepared.pop("research_content", None)
    chain = _compile_v8(
        task_type,
        scope=prepared,
        evidence_registry=evidence_registry,
        parent_chain_refs=parent_chain_refs,
    )
    if not isinstance(content, Mapping):
        return chain
    graph = chain.setdefault("reasoning_chain", {})
    nodes = graph.get("nodes") or []
    _apply_content_statements(nodes, content)
    _apply_premises(graph)
    _prefer_main_path(graph, content)
    _apply_premises(graph)
    nodes = propagate_node_status(
        nodes,
        graph.get("edges") or [],
        {
            str(row.get("evidence_id")): row
            for row in chain.get("evidence_registry") or []
            if row.get("evidence_id")
        },
    )
    graph["nodes"] = nodes
    node_ids = {str(node.get("node_id")) for node in nodes}
    targets = {
        str(edge.get("to_node_id"))
        for edge in graph.get("edges") or []
        if edge.get("to_node_id") in node_ids
    }
    graph["root_node_ids"] = sorted(node_ids - targets)
    main_path_set = set(graph.get("main_path_node_ids") or [])
    blockers = {
        str(node.get("node_id")): str(node.get("status"))
        for node in nodes
        if node.get("status") in {"EVIDENCE_MISSING", "CUTOFF_BLOCKED"}
    }
    main_blockers = [f"{blockers[node_id]}:{node_id}" for node_id in sorted(main_path_set & blockers.keys())]
    side_blockers = [f"{status}:{node_id}" for node_id, status in sorted(blockers.items()) if node_id not in main_path_set]
    gate = graph.setdefault("closure_gate", {})
    gate["blockers"] = main_blockers
    gate["side_branch_blockers"] = side_blockers
    gate["closure_scope"] = "MAIN_PATH"
    gate["graph_errors"] = validate_chain_graph(graph)
    gate["status"] = "CLOSED" if not main_blockers and not gate["graph_errors"] else ("CUTOFF_BLOCKED" if any(value.startswith("CUTOFF_BLOCKED:") for value in main_blockers) else "OPEN")
    chain["reasoning_chain"] = graph
    main_path = list(graph.get("main_path_node_ids") or [])
    chain["conclusion_lineage"]["main_path_node_ids"] = main_path
    chain["conclusion_lineage"]["final_node_id"] = graph.get("final_node_id")
    chain["conclusion_lineage"]["evidence_ids"] = sorted(
        {
            evidence_id
            for node in nodes
            if node.get("node_id") in set(main_path)
            for evidence_id in node.get("evidence_ids") or []
        }
    )
    chain["conclusion_lineage"]["closure_status"] = graph["closure_gate"]["status"]
    return chain


__all__ = ["compile_reasoning_chain", "render_chain_summary"]
