"""Seven-layer event-specific operating mechanism chains for companies."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


NODE_TYPES = (
    "EVENT_FACT",
    "BEHAVIOR_OR_POLICY_CHANGE",
    "OBSERVABLE_OPERATING_VARIABLE",
    "INDUSTRY_REVENUE_OR_COST_VARIABLE",
    "COMPANY_BUSINESS_EXPOSURE",
    "DIRECTION_ASSESSMENT",
    "PRICE_AND_CONFOUNDER_VERIFICATION",
)
FORBIDDEN_MACRO_CODES = (
    "DCOILWTICO",
    "DCOILBRENTEU",
    "SP500",
    "DEXCHUS",
    "VIXCLS",
)
HORIZONS = {"IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM"}
PROFILE_STATEMENT_FIELDS = {
    "BEHAVIOR_OR_POLICY_CHANGE": "behavior_or_policy_change",
    "OBSERVABLE_OPERATING_VARIABLE": "observable_operating_variable",
    "INDUSTRY_REVENUE_OR_COST_VARIABLE": "industry_revenue_or_cost_variable",
    "COMPANY_BUSINESS_EXPOSURE": "company_business_exposure",
    "DIRECTION_ASSESSMENT": "direction_assessment",
    "PRICE_AND_CONFOUNDER_VERIFICATION": "price_and_confounder_verification",
}


def _required_id(record: Mapping[str, Any], field: str) -> str:
    value = str(record.get(field) or "").strip()
    if not value:
        raise ValueError(f"MECHANISM_CHAIN_REFERENCE_MISSING:{field}")
    return value


def build_mechanism_chain(
    mapping: Mapping[str, Any],
    profile: Mapping[str, Any],
    *,
    binding_review: Mapping[str, Any],
    company_evidence: Sequence[Mapping[str, Any]],
    direction_assessment: Mapping[str, Any],
    market_window: Mapping[str, Any],
    relative_window: Mapping[str, Any],
    confounder: Mapping[str, Any],
    timeline_node: Mapping[str, Any],
) -> dict[str, Any]:
    mapping_id = _required_id(mapping, "mapping_id")
    if str(profile.get("mapping_id") or "") != mapping_id:
        raise ValueError("MECHANISM_PROFILE_MAPPING_MISMATCH")
    if str(timeline_node.get("event_id") or "") != str(mapping.get("event_id") or ""):
        raise ValueError("TIMELINE_EVENT_MISMATCH")

    event_evidence_ids = [str(value) for value in timeline_node.get("source_ids") or []]
    available_company_evidence_ids = {
        str(row.get("evidence_id"))
        for row in company_evidence
        if str(row.get("company_id") or "") == str(mapping.get("company_id") or "")
    }
    company_evidence_ids = [
        str(value) for value in profile.get("company_evidence_ids") or []
    ]
    if not company_evidence_ids or not set(company_evidence_ids) <= available_company_evidence_ids:
        raise ValueError("COMPANY_EXPOSURE_EVIDENCE_INVALID")
    if set(event_evidence_ids) & set(company_evidence_ids):
        raise ValueError("EVENT_COMPANY_EVIDENCE_ID_COLLISION")

    horizon_directions = dict(profile.get("horizon_directions") or {})
    conditions = list(profile.get("conditions") or [])
    invalidation_conditions = list(profile.get("invalidation_conditions") or [])
    operating_metrics = [dict(value) for value in profile.get("operating_metrics") or []]
    if set(horizon_directions) != HORIZONS:
        raise ValueError("MECHANISM_PROFILE_HORIZONS_INCOMPLETE")
    if not conditions or not invalidation_conditions:
        raise ValueError("MECHANISM_PROFILE_CONDITIONS_INCOMPLETE")
    if not operating_metrics or any(
        not metric.get("name") or not metric.get("unit") for metric in operating_metrics
    ):
        raise ValueError("MECHANISM_PROFILE_METRICS_INCOMPLETE")

    statements = {"EVENT_FACT": str(timeline_node.get("fact") or "").strip()}
    statements.update(
        {
            node_type: str(profile.get(field) or "").strip()
            for node_type, field in PROFILE_STATEMENT_FIELDS.items()
        }
    )
    if any(not statements[node_type] for node_type in NODE_TYPES):
        raise ValueError("MECHANISM_CHAIN_STATEMENT_MISSING")
    joined_text = " ".join(statements.values())
    if any(code in joined_text for code in FORBIDDEN_MACRO_CODES):
        raise ValueError("GENERIC_MACRO_CODE_IN_MECHANISM_CHAIN")

    verification_ids = [
        _required_id(market_window, "company_market_window_id"),
        _required_id(relative_window, "relative_window_id"),
        _required_id(confounder, "company_confounder_id"),
    ]
    evidence_by_type = {
        "EVENT_FACT": event_evidence_ids,
        "COMPANY_BUSINESS_EXPOSURE": company_evidence_ids,
        "PRICE_AND_CONFOUNDER_VERIFICATION": verification_ids,
    }
    nodes: list[dict[str, Any]] = []
    for index, node_type in enumerate(NODE_TYPES, start=1):
        node = {
            "node_id": f"mechanism-node-{mapping_id}-{index}",
            "node_type": node_type,
            "statement": statements[node_type],
            "evidence_ids": list(evidence_by_type.get(node_type, [])),
        }
        if node_type == "DIRECTION_ASSESSMENT":
            node.update(
                {
                    "direction": str(profile.get("direction") or "UNKNOWN"),
                    "decision_status": str(profile.get("decision_status") or "ABSTAIN"),
                    "direction_id": _required_id(direction_assessment, "direction_id"),
                }
            )
        nodes.append(node)

    edges = [
        {
            "edge_id": f"mechanism-edge-{mapping_id}-{index + 1}-{index + 2}",
            "from_node_id": nodes[index]["node_id"],
            "to_node_id": nodes[index + 1]["node_id"],
        }
        for index in range(len(nodes) - 1)
    ]
    return {
        "chain_id": f"company-mechanism-{mapping_id}",
        "mapping_id": mapping_id,
        "event_id": mapping["event_id"],
        "anchor_id": mapping["anchor_id"],
        "company_id": mapping["company_id"],
        "company_code": mapping["company_code"],
        "company_name": mapping["company_name"],
        "timeline_node_id": _required_id(timeline_node, "fast_node_id"),
        "primary_binding_id": _required_id(binding_review, "primary_binding_id"),
        "horizon_directions": horizon_directions,
        "conditions": conditions,
        "invalidation_conditions": invalidation_conditions,
        "operating_metrics": operating_metrics,
        "nodes": nodes,
        "edges": edges,
        "chain_status": "PROPOSED_COMPANY_MECHANISM",
        "review_status": "NEEDS_HUMAN_REVIEW",
        "formal_ready": False,
        "sha_gate": "DEFERRED",
        "price_selection_used": False,
    }
