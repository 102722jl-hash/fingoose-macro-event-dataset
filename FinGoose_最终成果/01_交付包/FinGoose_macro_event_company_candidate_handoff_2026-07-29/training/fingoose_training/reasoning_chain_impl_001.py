"""Compile auditable reasoning chains for FinGoose training records."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Mapping, Sequence


REASONING_CHAIN_VERSION = "v1"
ALLOWED_NODE_STATUSES = {
    "VERIFIED_SOURCE",
    "EVIDENCE_MISSING",
    "SUPPORTED_INFERENCE",
    "INFERENCE_ONLY",
    "CALCULATED_ONLY",
    "CUTOFF_BLOCKED",
}
CALCULATED_NODE_TYPES = {
    "CALCULATED_FACT",
    "MARKET_CALCULATION",
    "MARKET_VALIDATION",
    "PRICE_AND_CONFOUNDER_VERIFICATION",
    "PRICE_CONFOUNDER_AND_COUNTEREVIDENCE",
}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return [] if value in (None, "") else [value]


def _text(record: Mapping[str, Any]) -> str:
    for key in (
        "statement_zh",
        "statement",
        "fact_zh",
        "fact",
        "inference_zh",
        "calculation_zh",
        "direct_answer_zh",
        "research_conclusion_zh",
    ):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "待补充陈述。"


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.fromisoformat(value.strip()[:10])
        except ValueError:
            return None


def _after_cutoff(value: Any, cutoff: Any) -> bool:
    observed = _parse_time(value)
    limit = _parse_time(cutoff)
    if not observed or not limit:
        return False
    if observed.tzinfo is None and limit.tzinfo is not None:
        observed = observed.replace(tzinfo=limit.tzinfo)
    if limit.tzinfo is None and observed.tzinfo is not None:
        limit = limit.replace(tzinfo=observed.tzinfo)
    return observed > limit


def _source_fields(record: Mapping[str, Any]) -> dict[str, Any]:
    evidence_id = record.get("evidence_id") or record.get("source_id")
    source_record_ids = {
        str(value)
        for value in _as_list(record.get("source_record_ids"))
        if value
    }
    source_id = record.get("source_id")
    if source_id and str(source_id) != str(evidence_id):
        source_record_ids.add(str(source_id))
    fields = {
        "evidence_id": evidence_id,
        "title": record.get("title") or record.get("document_title"),
        "publisher": record.get("publisher") or record.get("issuer"),
        "original_quote": record.get("original_quote"),
        "locator": record.get("locator") or record.get("page_or_section_locator"),
        "source_url": record.get("source_url"),
        "snapshot_sha256": record.get("snapshot_sha256")
        or record.get("source_snapshot_sha256")
        or record.get("content_sha256"),
        "published_at": record.get("first_public_at") or record.get("published_at"),
    }
    if source_record_ids:
        fields["source_record_ids"] = sorted(source_record_ids)
    return fields


def _is_verifiable(record: Mapping[str, Any]) -> bool:
    return all(record.get(key) for key in ("original_quote", "locator", "source_url"))


def compile_evidence_registry(
    records: Sequence[Mapping[str, Any]],
    nodes: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for record in records:
        fields = _source_fields(record)
        evidence_id = fields.pop("evidence_id", None)
        if not evidence_id:
            continue
        current = merged.setdefault(str(evidence_id), {"evidence_id": str(evidence_id)})
        source_record_ids = fields.pop("source_record_ids", [])
        if source_record_ids:
            current["source_record_ids"] = sorted(
                set(current.get("source_record_ids") or [])
                | set(source_record_ids)
            )
        for key, value in fields.items():
            if value not in (None, "") and current.get(key) in (None, ""):
                current[key] = deepcopy(value)

    for node in nodes:
        node_id = str(node.get("node_id") or "")
        for evidence_id in _as_list(node.get("evidence_ids")):
            evidence_id = str(evidence_id)
            current = merged.setdefault(evidence_id, {"evidence_id": evidence_id})
            supports = current.setdefault("supports_node_ids", [])
            if node_id and node_id not in supports:
                supports.append(node_id)

    result = []
    for evidence_id in sorted(merged):
        record = merged[evidence_id]
        record["supports_node_ids"] = sorted(record.get("supports_node_ids", []))
        record["missing"] = not _is_verifiable(record)
        result.append(record)
    return result


def _node_is_calculated(node: Mapping[str, Any]) -> bool:
    node_type = str(node.get("node_type") or "").upper()
    statement_class = str(node.get("statement_class") or "").upper()
    return statement_class == "CALCULATED_FACT" or node_type in CALCULATED_NODE_TYPES


def _node_is_source(node: Mapping[str, Any]) -> bool:
    return str(node.get("statement_class") or "").upper() == "SOURCE_FACT"


def _normalized_nodes(nodes: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, source in enumerate(nodes, start=1):
        node = deepcopy(dict(source))
        node["node_id"] = str(node.get("node_id") or f"reasoning-node-{index}")
        node["node_type"] = str(node.get("node_type") or "RESEARCH_INFERENCE")
        node["statement_zh"] = _text(node)
        node["evidence_ids"] = sorted(
            {str(value) for value in _as_list(node.get("evidence_ids")) if value}
        )
        node["premise_node_ids"] = sorted(
            {str(value) for value in _as_list(node.get("premise_node_ids")) if value}
        )
        normalized.append(node)
    return normalized


def propagate_node_status(
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    result = _normalized_nodes(nodes)
    by_id = {node["node_id"]: node for node in result}
    cutoff = next((node.get("prediction_cutoff_at") for node in result if node.get("prediction_cutoff_at")), None)
    incoming: dict[str, list[str]] = {node_id: [] for node_id in by_id}
    for edge in edges:
        source = str(edge.get("from_node_id") or "")
        target = str(edge.get("to_node_id") or "")
        if source in by_id and target in by_id and source not in incoming[target]:
            incoming[target].append(source)

    unresolved = set(by_id)
    while unresolved:
        progressed = False
        for node in result:
            node_id = node["node_id"]
            if node_id not in unresolved:
                continue
            premises = node.get("premise_node_ids") or incoming.get(node_id, [])
            pending = [value for value in premises if value in unresolved]
            if pending:
                continue
            evidence_ids = node.get("evidence_ids") or []
            evidence = [evidence_by_id[value] for value in evidence_ids if value in evidence_by_id]
            valid_evidence = [record for record in evidence if not record.get("missing")]
            node_time = node.get("published_at") or node.get("first_public_at")
            evidence_times = [record.get("published_at") for record in valid_evidence if record.get("published_at")]
            blocked = _after_cutoff(node_time, cutoff) or (
                bool(valid_evidence)
                and bool(evidence_times)
                and all(_after_cutoff(value, cutoff) for value in evidence_times)
            )
            if blocked:
                status = "CUTOFF_BLOCKED"
            elif _node_is_calculated(node):
                status = "CALCULATED_ONLY"
            elif _node_is_source(node):
                status = "VERIFIED_SOURCE" if valid_evidence else "EVIDENCE_MISSING"
            else:
                premise_statuses = [by_id[value].get("status") for value in premises if value in by_id]
                supported = bool(premises) and len(premise_statuses) == len(premises) and all(
                    value in {"VERIFIED_SOURCE", "SUPPORTED_INFERENCE"}
                    for value in premise_statuses
                )
                status = "SUPPORTED_INFERENCE" if supported or valid_evidence else "INFERENCE_ONLY"
            node["status"] = status
            unresolved.remove(node_id)
            progressed = True
        if progressed:
            continue
        for node_id in sorted(unresolved):
            by_id[node_id]["status"] = "INFERENCE_ONLY"
        break
    return result


def _normalize_edges(
    edges: Sequence[Mapping[str, Any]], nodes: Sequence[Mapping[str, Any]]
) -> list[dict[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for edge in edges:
        source = edge.get("from_node_id")
        target = edge.get("to_node_id")
        if source and target:
            pairs.add((str(source), str(target)))
    for node in nodes:
        target = str(node.get("node_id") or "")
        for source in _as_list(node.get("premise_node_ids")):
            if source and target:
                pairs.add((str(source), target))
    return [
        {"from_node_id": source, "to_node_id": target}
        for source, target in sorted(pairs)
    ]


def _topological_order(nodes: Sequence[Mapping[str, Any]], edges: Sequence[Mapping[str, Any]]) -> list[str]:
    node_ids = [str(node.get("node_id")) for node in nodes]
    incoming = {node_id: 0 for node_id in node_ids}
    outgoing = {node_id: [] for node_id in node_ids}
    for edge in edges:
        source = str(edge.get("from_node_id") or "")
        target = str(edge.get("to_node_id") or "")
        if source in outgoing and target in incoming:
            outgoing[source].append(target)
            incoming[target] += 1
    ready = sorted(node_id for node_id, count in incoming.items() if count == 0)
    order: list[str] = []
    while ready:
        node_id = ready.pop(0)
        order.append(node_id)
        for target in sorted(outgoing[node_id]):
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)
                ready.sort()
    return order


def _reachable(start_ids: Sequence[str], edges: Sequence[Mapping[str, Any]]) -> set[str]:
    outgoing: dict[str, list[str]] = {}
    for edge in edges:
        outgoing.setdefault(str(edge.get("from_node_id")), []).append(str(edge.get("to_node_id")))
    seen = set(start_ids)
    stack = list(start_ids)
    while stack:
        current = stack.pop()
        for target in outgoing.get(current, []):
            if target not in seen:
                seen.add(target)
                stack.append(target)
    return seen


def validate_chain_graph(chain: Mapping[str, Any]) -> list[str]:
    graph = chain.get("reasoning_chain") if isinstance(chain.get("reasoning_chain"), Mapping) else chain
    nodes = graph.get("nodes") if isinstance(graph, Mapping) else []
    edges = graph.get("edges") if isinstance(graph, Mapping) else []
    node_ids = [node.get("node_id") for node in nodes if isinstance(node, Mapping)]
    codes: list[str] = []
    if len(node_ids) != len(set(node_ids)):
        codes.append("REASONING_NODE_DUPLICATE")
    known = set(node_ids)
    if any(edge.get("from_node_id") not in known or edge.get("to_node_id") not in known for edge in edges if isinstance(edge, Mapping)):
        codes.append("REASONING_EDGE_UNKNOWN_NODE")
    if len(_topological_order(nodes, edges)) != len(nodes):
        codes.append("REASONING_GRAPH_CYCLE")
    final_node_id = graph.get("final_node_id") if isinstance(graph, Mapping) else None
    root_ids = graph.get("root_node_ids") or [] if isinstance(graph, Mapping) else []
    if final_node_id not in known or (root_ids and final_node_id not in _reachable(root_ids, edges)):
        codes.append("REASONING_FINAL_UNREACHABLE")
    return codes
