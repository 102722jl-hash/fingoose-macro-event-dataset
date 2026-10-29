"""Candidate-completion gates for event-to-company impact records."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


HORIZONS = ("IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM")
WINDOWS = ("T_MINUS_1", "T0", "D1", "D3", "D5", "D20")
DOSSIER_CATEGORIES = {
    "BUSINESS_STRUCTURE",
    "GEOGRAPHIC_EXPOSURE",
    "DEMAND_SENSITIVITY",
    "COST_SENSITIVITY",
    "LIMITATIONS_AND_COUNTEREVIDENCE",
}
DIRECTIONS = {"POSITIVE", "NEGATIVE", "MIXED", "UNKNOWN"}
MECHANISM_NODE_TYPES = (
    "EVENT_FACT",
    "BEHAVIOR_OR_POLICY_CHANGE",
    "OBSERVABLE_OPERATING_VARIABLE",
    "INDUSTRY_REVENUE_OR_COST_VARIABLE",
    "COMPANY_BUSINESS_EXPOSURE",
    "DIRECTION_ASSESSMENT",
    "PRICE_AND_CONFOUNDER_VERIFICATION",
)


def build_binding_review(
    mapping: Mapping[str, Any],
    *,
    primary_binding_id: str,
    secondary_binding_ids: Sequence[str],
    rejected_bindings: Mapping[str, str],
    selection_basis: str,
    evidence_ids: Sequence[str],
    counterevidence_ids: Sequence[str],
) -> dict[str, Any]:
    candidates = [str(value) for value in mapping.get("candidate_binding_ids") or []]
    candidate_set = set(candidates)
    secondary = [str(value) for value in secondary_binding_ids]
    selected = [primary_binding_id, *secondary]
    if not primary_binding_id or primary_binding_id not in candidate_set:
        raise ValueError("PRIMARY_BINDING_NOT_IN_CANDIDATES")
    if len(secondary) > 2:
        raise ValueError("SECONDARY_BINDING_LIMIT_EXCEEDED")
    if len(set(selected)) != len(selected):
        raise ValueError("DUPLICATE_SELECTED_BINDING")
    if any(value not in candidate_set for value in secondary):
        raise ValueError("SECONDARY_BINDING_NOT_IN_CANDIDATES")
    expected_rejected = candidate_set - set(selected)
    if set(rejected_bindings) != expected_rejected:
        raise ValueError("INCOMPLETE_BINDING_DISPOSITION")
    if any(not str(reason).strip() for reason in rejected_bindings.values()):
        raise ValueError("REJECTED_BINDING_REASON_REQUIRED")
    if not selection_basis.strip():
        raise ValueError("BINDING_SELECTION_BASIS_REQUIRED")
    if not evidence_ids:
        raise ValueError("BINDING_EVIDENCE_REQUIRED")

    return {
        "mapping_id": mapping["mapping_id"],
        "event_id": mapping["event_id"],
        "anchor_id": mapping["anchor_id"],
        "primary_binding_id": primary_binding_id,
        "secondary_binding_ids": secondary,
        "rejected_bindings": [
            {"binding_id": binding_id, "reason": rejected_bindings[binding_id]}
            for binding_id in candidates
            if binding_id in rejected_bindings
        ],
        "selection_basis": selection_basis,
        "evidence_ids": list(evidence_ids),
        "counterevidence_ids": list(counterevidence_ids),
        "binding_selection_complete": True,
        "price_selection_used": False,
        "review_status": "NEEDS_HUMAN_REVIEW",
        "formal_ready": False,
    }


def build_horizon_reviews(
    horizons: Mapping[str, str],
    *,
    abstentions: Mapping[str, Mapping[str, Any]] | None = None,
    conditions: Sequence[str] = (),
    invalidation_conditions: Sequence[str] = (),
    evidence_ids: Sequence[str] = (),
    counterevidence_ids: Sequence[str] = (),
) -> dict[str, dict[str, Any]]:
    abstentions = abstentions or {}
    result: dict[str, dict[str, Any]] = {}
    for horizon in HORIZONS:
        direction = str(horizons.get(horizon) or "")
        if direction not in DIRECTIONS:
            raise ValueError(f"INVALID_DIRECTION:{horizon}:{direction}")
        if direction == "UNKNOWN":
            abstention = abstentions.get(horizon) or {}
            reason = str(abstention.get("reason") or "").strip()
            missing = list(abstention.get("missing_evidence") or [])
            if not reason or not missing:
                raise ValueError(f"UNEXPLAINED_UNKNOWN_DIRECTION:{horizon}")
            result[horizon] = {
                "direction": direction,
                "decision_status": "ABSTAIN",
                "abstention_reason": reason,
                "missing_evidence": missing,
            }
        else:
            result[horizon] = {
                "direction": direction,
                "decision_status": "DIRECTIONAL_CANDIDATE",
                "abstention_reason": None,
                "missing_evidence": [],
            }
        result[horizon].update(
            {
                "conditions": list(conditions),
                "invalidation_conditions": list(invalidation_conditions),
                "evidence_ids": list(evidence_ids),
                "counterevidence_ids": list(counterevidence_ids),
            }
        )
    return result


def _dossier_complete(dossier: Mapping[str, Any]) -> bool:
    categories = {
        str(row.get("category")): row
        for row in dossier.get("research_categories") or []
    }
    if set(categories) != DOSSIER_CATEGORIES:
        return False
    for row in categories.values():
        status = row.get("status")
        if status == "EVIDENCE_SUPPORTED" and not row.get("evidence_ids"):
            return False
        if status == "NOT_DISCLOSED_AFTER_SEARCH" and not row.get("search_audit_ids"):
            return False
        if status not in {"EVIDENCE_SUPPORTED", "NOT_DISCLOSED_AFTER_SEARCH"}:
            return False
    return True


def _direction_complete(direction: Mapping[str, Any]) -> bool:
    reviews = direction.get("horizon_reviews") or {}
    if set(reviews) != set(HORIZONS):
        return False
    for review in reviews.values():
        if review.get("decision_status") == "ABSTAIN":
            if not review.get("abstention_reason") or not review.get("missing_evidence"):
                return False
        elif review.get("decision_status") != "DIRECTIONAL_CANDIDATE":
            return False
    return True


def _company_window_complete(window: Mapping[str, Any]) -> bool:
    observations = window.get("observations") or {}
    return all(
        observations.get(horizon, {}).get("status") == "OBSERVED"
        for horizon in WINDOWS
    )


def _industry_window_complete(window: Mapping[str, Any]) -> bool:
    if not window.get("industry_benchmark_id"):
        return False
    observations = window.get("observations") or {}
    return all(
        observations.get(horizon, {}).get("industry_status") == "AVAILABLE"
        and observations.get(horizon, {}).get("industry_relative_return") is not None
        for horizon in WINDOWS
    )


def _mechanism_chain_complete(chain: Mapping[str, Any]) -> bool:
    nodes = list(chain.get("nodes") or [])
    edges = list(chain.get("edges") or [])
    if [node.get("node_type") for node in nodes] != list(MECHANISM_NODE_TYPES):
        return False
    node_ids = [str(node.get("node_id") or "") for node in nodes]
    if any(not node_id for node_id in node_ids) or len(set(node_ids)) != len(node_ids):
        return False
    expected_edges = list(zip(node_ids, node_ids[1:]))
    actual_edges = [
        (str(edge.get("from_node_id") or ""), str(edge.get("to_node_id") or ""))
        for edge in edges
    ]
    return actual_edges == expected_edges


def evaluate_completion(
    *,
    mapping_id: str,
    binding_review: Mapping[str, Any],
    dossier: Mapping[str, Any],
    direction: Mapping[str, Any],
    market_window: Mapping[str, Any],
    relative_window: Mapping[str, Any],
    confounder: Mapping[str, Any],
    mechanism_chain: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []
    if not binding_review.get("binding_selection_complete"):
        blockers.append("BINDING_REVIEW_INCOMPLETE")
    if not _dossier_complete(dossier):
        blockers.append("DOSSIER_RESEARCH_INCOMPLETE")
    if not _direction_complete(direction):
        blockers.append("DIRECTION_HORIZONS_INCOMPLETE")
    if not _company_window_complete(market_window):
        blockers.append("COMPANY_WINDOW_INCOMPLETE")
    if not _industry_window_complete(relative_window):
        blockers.append("INDUSTRY_WINDOW_INCOMPLETE")
    if confounder.get("company_confounder_status") != "REVIEWED":
        blockers.append("CONFOUNDER_REVIEW_INCOMPLETE")
    if not _mechanism_chain_complete(mechanism_chain or {}):
        blockers.append("MECHANISM_CHAIN_INCOMPLETE")
    if confounder.get("suspension_status") not in {
        "VERIFIED_TRADING",
        "VERIFIED_SUSPENDED",
    }:
        blockers.append("SUSPENSION_REVIEW_INCOMPLETE")
    if any(
        record.get("review_status") not in {None, "NEEDS_HUMAN_REVIEW"}
        for record in (binding_review, dossier, direction, confounder)
    ):
        blockers.append("REVIEW_BOUNDARY_VIOLATION")

    return {
        "mapping_id": mapping_id,
        "completion_status": "CANDIDATE_COMPLETE" if not blockers else "OPEN",
        "blockers": blockers,
        "review_status": "NEEDS_HUMAN_REVIEW",
        "formal_ready": False,
    }
