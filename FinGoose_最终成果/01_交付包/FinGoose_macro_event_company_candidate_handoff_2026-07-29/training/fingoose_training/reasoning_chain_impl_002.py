"""Task-specific chain compilation built on the v1 graph primitives."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .reasoning_chain_impl_001 import (
    REASONING_CHAIN_VERSION,
    _as_list,
    _normalize_edges,
    _normalized_nodes,
    _text,
    _topological_order,
    compile_evidence_registry,
    propagate_node_status,
    validate_chain_graph,
)


def _event_nodes(scope: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for index, milestone in enumerate(_as_list(scope.get("milestones")), start=1):
        if not isinstance(milestone, Mapping):
            continue
        evidence_ids = [
            source.get("evidence_id")
            for source in _as_list(milestone.get("sources"))
            if isinstance(source, Mapping) and source.get("evidence_id")
        ]
        nodes.append(
            {
                **deepcopy(dict(milestone)),
                "node_id": str(milestone.get("milestone_id") or f"event-milestone-{index}"),
                "node_type": "EVENT_FACT",
                "statement_class": "SOURCE_FACT",
                "statement_zh": _text(milestone),
                "evidence_ids": evidence_ids,
            }
        )
    for graph in _as_list(scope.get("transmission_graphs")):
        if not isinstance(graph, Mapping):
            continue
        for raw_node in _as_list(graph.get("nodes")):
            if isinstance(raw_node, Mapping):
                node = deepcopy(dict(raw_node))
                node.setdefault("statement_class", "RESEARCH_INFERENCE")
                nodes.append(node)
        edges.extend(
            deepcopy(dict(edge))
            for edge in _as_list(graph.get("edges"))
            if isinstance(edge, Mapping)
        )
    if scope.get("market_windows"):
        premises = [str(nodes[-1].get("node_id"))] if nodes else []
        nodes.append(
            {
                "node_id": f"{scope.get('event_id', 'event')}-market-validation",
                "node_type": "MARKET_VALIDATION",
                "statement_class": "CALCULATED_FACT",
                "statement_zh": "固定行情窗口用于验证市场反应，不证明严格因果。",
                "premise_node_ids": premises,
            }
        )
    if not nodes:
        nodes = [
            {
                "node_id": f"{scope.get('event_id', 'event')}-boundary",
                "node_type": "DIRECTION_ASSESSMENT",
                "statement_class": "RESEARCH_INFERENCE",
                "statement_zh": "事件结论证据不足，保持候选边界。",
            }
        ]
    return nodes, edges


def _qa_nodes(scope: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    case = scope.get("case") if isinstance(scope.get("case"), Mapping) else {}
    answer = scope.get("answer") if isinstance(scope.get("answer"), Mapping) else scope
    case_id = str(scope.get("case_id") or case.get("case_id") or "qa")
    nodes: list[dict[str, Any]] = []
    for index, record in enumerate(_as_list(answer.get("evidence"))[:6], start=1):
        if not isinstance(record, Mapping):
            continue
        evidence_id = record.get("evidence_id") or record.get("source_id")
        nodes.append(
            {
                "node_id": f"{case_id}-source-{index}",
                "node_type": "QA_SOURCE_FACT",
                "statement_class": "SOURCE_FACT",
                "statement_zh": record.get("fact_zh") or record.get("original_quote") or "问题相关来源。",
                "evidence_ids": [evidence_id] if evidence_id else [],
            }
        )
    task_answer = answer.get("task_answer") if isinstance(answer.get("task_answer"), Mapping) else {}
    inference_values = _as_list(task_answer.get("research_inferences")) or _as_list(answer.get("mechanism_chain"))
    premise_ids = [str(node["node_id"]) for node in nodes]
    for index, record in enumerate(inference_values[:4], start=1):
        item = record if isinstance(record, Mapping) else {"statement_zh": str(record)}
        node_id = f"{case_id}-inference-{index}"
        nodes.append(
            {
                "node_id": node_id,
                "node_type": "QA_RESEARCH_INFERENCE",
                "statement_class": "RESEARCH_INFERENCE",
                "statement_zh": _text(item),
                "evidence_ids": _as_list(item.get("evidence_ids")),
                "premise_node_ids": premise_ids[-3:],
            }
        )
        premise_ids.append(node_id)
    if answer.get("market_windows") or task_answer.get("calculated_facts"):
        node_id = f"{case_id}-calculation"
        nodes.append(
            {
                "node_id": node_id,
                "node_type": "MARKET_VALIDATION",
                "statement_class": "CALCULATED_FACT",
                "statement_zh": "问题相关计算事实只用于验证。",
                "premise_node_ids": premise_ids[-1:],
            }
        )
        premise_ids.append(node_id)
    direct_answer = task_answer.get("direct_answer_zh") or answer.get("research_conclusion_zh") or "证据不足，保持候选回答。"
    nodes.append(
        {
            "node_id": f"{case_id}-conclusion",
            "node_type": "DIRECTION_ASSESSMENT",
            "statement_class": "RESEARCH_INFERENCE",
            "statement_zh": str(direct_answer),
            "premise_node_ids": premise_ids[-3:],
        }
    )
    return nodes, []


def _scope_id(task_type: str, scope: Mapping[str, Any]) -> str:
    keys = {
        "EVENT_ANALYSIS": ("event_id", "scope_id"),
        "INDUSTRY_IMPACT": ("event_industry_mapping_id", "scope_id"),
        "COMPANY_IMPACT": ("mapping_id", "scope_id", "company_code"),
        "EVENT_QA": ("case_id", "scope_id"),
    }.get(task_type, ("scope_id", "event_id"))
    for key in keys:
        if scope.get(key):
            return str(scope[key])
    return f"{task_type.lower()}-unknown"


def _extract_nodes_and_edges(task_type: str, scope: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if isinstance(scope.get("nodes"), list):
        return deepcopy(scope["nodes"]), deepcopy(_as_list(scope.get("edges")))
    mechanism = scope.get("mechanism_chain")
    if isinstance(mechanism, Mapping) and isinstance(mechanism.get("nodes"), list):
        return deepcopy(mechanism["nodes"]), deepcopy(_as_list(mechanism.get("edges")))
    if task_type == "EVENT_ANALYSIS":
        return _event_nodes(scope)
    if task_type == "EVENT_QA":
        return _qa_nodes(scope)
    return [
        {
            "node_id": f"{_scope_id(task_type, scope)}-boundary",
            "node_type": "DIRECTION_ASSESSMENT",
            "statement_class": "RESEARCH_INFERENCE",
            "statement_zh": "当前范围缺少完整机制节点，保持候选边界。",
        }
    ], []


def _longest_path(nodes: Sequence[Mapping[str, Any]], edges: Sequence[Mapping[str, Any]], roots: Sequence[str], final_node_id: str) -> list[str]:
    allowed = {str(node.get("node_id")) for node in nodes if node.get("status") != "CUTOFF_BLOCKED"}
    incoming: dict[str, list[str]] = {node_id: [] for node_id in allowed}
    for edge in edges:
        source = str(edge.get("from_node_id"))
        target = str(edge.get("to_node_id"))
        if source in allowed and target in allowed:
            incoming[target].append(source)
    paths: dict[str, list[str]] = {}
    for node_id in _topological_order(nodes, edges):
        if node_id not in allowed:
            continue
        candidates = [paths[source] for source in incoming.get(node_id, []) if source in paths]
        if candidates:
            paths[node_id] = max(candidates, key=lambda value: (len(value), value)) + [node_id]
        elif node_id in roots or not incoming.get(node_id):
            paths[node_id] = [node_id]
    return paths.get(final_node_id, [])


def compile_reasoning_chain(task_type: str, *, scope: Mapping[str, Any], evidence_registry: Sequence[Mapping[str, Any]], parent_chain_refs: Sequence[str] = ()) -> dict[str, Any]:
    raw_nodes, raw_edges = _extract_nodes_and_edges(task_type, scope)
    nodes = _normalized_nodes(raw_nodes)
    cutoff = scope.get("prediction_cutoff_at")
    if not cutoff and isinstance(scope.get("case"), Mapping):
        cutoff = scope["case"].get("prediction_cutoff_at")
    for node in nodes:
        node["prediction_cutoff_at"] = cutoff
    edges = _normalize_edges(raw_edges, nodes)
    registry = compile_evidence_registry(evidence_registry, nodes)
    nodes = propagate_node_status(nodes, edges, {row["evidence_id"]: row for row in registry})
    node_ids = [node["node_id"] for node in nodes]
    targets = {edge["to_node_id"] for edge in edges}
    roots = [node_id for node_id in node_ids if node_id not in targets]
    topo = _topological_order(nodes, edges)
    requested_final = scope.get("final_node_id")
    if not requested_final and isinstance(scope.get("mechanism_chain"), Mapping):
        requested_final = scope["mechanism_chain"].get("final_node_id")
    final_node_id = str(requested_final or (topo[-1] if topo else node_ids[-1]))
    main_path = _longest_path(nodes, edges, roots, final_node_id)
    blocked = [node["node_id"] for node in nodes if node["status"] == "CUTOFF_BLOCKED"]
    missing = [node["node_id"] for node in nodes if node["status"] == "EVIDENCE_MISSING"]
    blockers = [*(f"CUTOFF_BLOCKED:{node_id}" for node_id in blocked), *(f"EVIDENCE_MISSING:{node_id}" for node_id in missing)]
    if not main_path:
        blockers.append("MAIN_PATH_INCOMPLETE")
    graph = {
        "task_type": task_type,
        "scope_id": _scope_id(task_type, scope),
        "nodes": nodes,
        "edges": edges,
        "root_node_ids": roots,
        "main_path_node_ids": main_path,
        "side_branch_node_ids": sorted(set(node_ids) - set(main_path)),
        "final_node_id": final_node_id,
        "closure_gate": {"status": "CLOSED" if not blockers else ("CUTOFF_BLOCKED" if blocked else "OPEN"), "blockers": blockers},
    }
    graph_errors = validate_chain_graph(graph)
    graph["closure_gate"]["graph_errors"] = graph_errors
    if graph_errors:
        graph["closure_gate"]["status"] = "OPEN"
    return {
        "reasoning_chain_version": REASONING_CHAIN_VERSION,
        "parent_chain_refs": sorted({str(value) for value in parent_chain_refs if value}),
        "evidence_registry": registry,
        "reasoning_chain": graph,
        "conclusion_lineage": {
            "scope_id": graph["scope_id"],
            "final_node_id": final_node_id,
            "main_path_node_ids": main_path,
            "evidence_ids": sorted({evidence_id for node in nodes if node["node_id"] in main_path for evidence_id in node.get("evidence_ids", [])}),
            "closure_status": graph["closure_gate"]["status"],
        },
    }


def render_chain_summary(chain: Mapping[str, Any]) -> str:
    graph = chain.get("reasoning_chain") or {}
    nodes = {node.get("node_id"): node for node in graph.get("nodes", [])}
    lines = ["推理链主路径："]
    for index, node_id in enumerate(graph.get("main_path_node_ids", [])[:7], start=1):
        node = nodes.get(node_id) or {}
        statement = str(node.get("statement_zh") or "待补充陈述。")
        if len(statement) > 90:
            statement = statement[:87].rstrip() + "..."
        evidence = "、".join(node.get("evidence_ids") or []) or "无直接证据"
        lines.append(f"{index}. [{node.get('status', 'UNKNOWN')}] {statement}（证据 ID：{evidence}）")
    gate = graph.get("closure_gate") or {}
    blockers = gate.get("blockers") or []
    boundary = "无强制缺口" if not blockers else "；".join(blockers[:4])
    lines.append(f"证据边界：{boundary}；行情与公式节点只用于验证，不单独证明因果。")
    return "\n".join(lines)


__all__ = ["compile_reasoning_chain", "render_chain_summary"]
