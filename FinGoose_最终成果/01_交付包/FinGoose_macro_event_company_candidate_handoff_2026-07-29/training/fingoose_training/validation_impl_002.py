"""Extend legacy dataset validation with reasoning-chain release gates."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from .reasoning_chain import ALLOWED_NODE_STATUSES, validate_chain_graph
from .validation_impl_001 import (
    ALLOWED_SPLITS,
    ALLOWED_TASK_TYPES,
    EXPECTED_ROLES,
    FORBIDDEN_TOKENS,
    MAX_MESSAGE_CHARS,
    METADATA_LIST_FIELDS,
    TRUNCATION_MARKER,
    _issue,
    validate_datasets as _validate_v1,
)


REASONING_METADATA_FIELDS = {
    "reasoning_chain_version",
    "evidence_registry",
    "reasoning_chain",
    "conclusion_lineage",
}


def _reasoning_codes(metadata: Mapping[str, Any], task_type: str | None) -> list[str]:
    present = REASONING_METADATA_FIELDS & set(metadata)
    if not present:
        return []
    codes: list[str] = []
    if metadata.get("reasoning_chain_version") != "v1" or not REASONING_METADATA_FIELDS <= set(metadata):
        codes.append("REASONING_SCHEMA_MISSING")
        return codes
    graph = metadata.get("reasoning_chain")
    registry = metadata.get("evidence_registry")
    lineage = metadata.get("conclusion_lineage")
    if not isinstance(graph, Mapping) or not isinstance(registry, list) or not isinstance(lineage, Mapping):
        return ["REASONING_SCHEMA_INVALID"]
    codes.extend(validate_chain_graph(graph))
    nodes = [node for node in graph.get("nodes", []) if isinstance(node, Mapping)]
    node_ids = {node.get("node_id") for node in nodes}
    if any(not isinstance(node.get("node_id"), str) or node.get("status") not in ALLOWED_NODE_STATUSES for node in nodes):
        codes.append("REASONING_NODE_INVALID")

    registry_by_id = {
        row.get("evidence_id"): row
        for row in registry
        if isinstance(row, Mapping) and isinstance(row.get("evidence_id"), str)
    }
    expected_supports: dict[str, set[str]] = {}
    for node in nodes:
        evidence_ids = node.get("evidence_ids") or []
        if not isinstance(evidence_ids, list) or not all(isinstance(value, str) for value in evidence_ids):
            codes.append("REASONING_EVIDENCE_LINK_MISMATCH")
            continue
        for evidence_id in evidence_ids:
            expected_supports.setdefault(evidence_id, set()).add(str(node.get("node_id")))
            if evidence_id not in registry_by_id:
                codes.append("REASONING_EVIDENCE_LINK_MISMATCH")
    for evidence_id, row in registry_by_id.items():
        supports = row.get("supports_node_ids") or []
        if not isinstance(supports, list) or set(supports) != expected_supports.get(evidence_id, set()) or not set(supports) <= node_ids:
            codes.append("REASONING_EVIDENCE_LINK_MISMATCH")
        if row.get("missing") and any(row.get(key) for key in ("original_quote", "source_url")):
            codes.append("REASONING_MISSING_EVIDENCE_FABRICATED")

    if task_type == "INDUSTRY_IMPACT" and len(nodes) != 7:
        codes.append("REASONING_INDUSTRY_NODE_COUNT")
    if task_type == "COMPANY_IMPACT" and not any("COMPANY_BUSINESS_EXPOSURE" in str(node.get("node_type")) for node in nodes):
        codes.append("REASONING_COMPANY_EXPOSURE_MISSING")
    main_path = set(graph.get("main_path_node_ids") or [])
    if any(node.get("status") == "CUTOFF_BLOCKED" and node.get("node_id") in main_path for node in nodes):
        codes.append("REASONING_CUTOFF_IN_MAIN_PATH")
    status_by_id = {node.get("node_id"): node.get("status") for node in nodes}
    for node in nodes:
        premises = node.get("premise_node_ids") or []
        if premises and all(status_by_id.get(value) == "CALCULATED_ONLY" for value in premises) and node.get("status") != "CALCULATED_ONLY":
            codes.append("REASONING_CALCULATION_SOLE_PREMISE")
    if lineage.get("final_node_id") != graph.get("final_node_id"):
        codes.append("REASONING_LINEAGE_MISMATCH")
    return sorted(set(codes))


def validate_reasoning_chain(metadata: Mapping[str, Any], task_type: str | None = None) -> list[str]:
    """Return stable public error codes for a projected reasoning chain."""

    return _reasoning_codes(metadata, task_type)


def _reasoning_stats(samples: list[dict[str, Any]]) -> dict[str, Any]:
    by_task: dict[str, Counter[str]] = {}
    totals = Counter()
    for sample in samples:
        metadata = sample.get("metadata") or {}
        graph = metadata.get("reasoning_chain")
        registry = metadata.get("evidence_registry")
        if not isinstance(graph, Mapping) or not isinstance(registry, list):
            continue
        task = str(sample.get("task_type") or "UNKNOWN")
        stats = by_task.setdefault(task, Counter())
        nodes = [node for node in graph.get("nodes", []) if isinstance(node, Mapping)]
        values = {
            "chain_count": 1,
            "node_count": len(nodes),
            "missing_node_count": sum(node.get("status") == "EVIDENCE_MISSING" for node in nodes),
            "main_path_node_count": len(graph.get("main_path_node_ids") or []),
            "evidence_count": len(registry),
            "open_closure_count": int((graph.get("closure_gate") or {}).get("status") != "CLOSED"),
        }
        stats.update(values)
        totals.update(values)
    return {
        "totals": dict(sorted(totals.items())),
        "by_task": {key: dict(sorted(value.items())) for key, value in sorted(by_task.items())},
    }


def validate_datasets(
    unified_events: list[dict[str, Any]],
    sft_samples: list[dict[str, Any]],
    expected_events: set[str],
    expected_task_types: set[str] | None = None,
) -> dict[str, Any]:
    report = _validate_v1(
        unified_events,
        sft_samples,
        expected_events,
        expected_task_types=expected_task_types,
    )
    reasoning_errors: list[dict[str, Any]] = []
    for sample in sft_samples:
        metadata = sample.get("metadata")
        if not isinstance(metadata, Mapping):
            continue
        for code in _reasoning_codes(metadata, sample.get("task_type")):
            reasoning_errors.append(
                _issue(code, "规范推理链未通过发布门禁。", sample.get("sample_id"))
            )
    report["errors"].extend(reasoning_errors)
    report["valid"] = not report["errors"]
    report["reasoning_chain_stats"] = _reasoning_stats(sft_samples)
    return report


__all__ = [
    "ALLOWED_SPLITS",
    "ALLOWED_TASK_TYPES",
    "EXPECTED_ROLES",
    "FORBIDDEN_TOKENS",
    "MAX_MESSAGE_CHARS",
    "METADATA_LIST_FIELDS",
    "TRUNCATION_MARKER",
    "validate_datasets",
    "validate_reasoning_chain",
]
