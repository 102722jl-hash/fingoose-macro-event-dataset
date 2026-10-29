"""Direction assessment contracts for company-impact v2."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from fingoose_company_impact_io_v2 import make_id


HORIZONS = ("IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM")
ALLOWED_DIRECTIONS = {"POSITIVE", "NEGATIVE", "MIXED", "NEUTRAL", "UNKNOWN"}


def build_direction(
    mapping: Mapping[str, Any],
    *,
    horizons: Mapping[str, str],
    mechanism: str | None,
    claim_ids: Iterable[str],
    evidence: Iterable[Mapping[str, Any]] = (),
    conditions: Iterable[str] = (),
    invalidation_conditions: Iterable[str] = (),
    counterevidence_ids: Iterable[str] = (),
    confidence: str = "LOW",
) -> dict[str, Any]:
    evidence_rows = [dict(row) for row in evidence]
    if any(row.get("kind") == "PRICE_OUTCOME" for row in evidence_rows):
        raise ValueError("POST_EVENT_PRICE_LEAKAGE")
    normalized_claim_ids = [str(value) for value in claim_ids]
    normalized_horizons = {
        horizon: str(horizons.get(horizon, "UNKNOWN")) for horizon in HORIZONS
    }
    invalid = set(normalized_horizons.values()) - ALLOWED_DIRECTIONS
    if invalid:
        raise ValueError(f"INVALID_DIRECTION:{sorted(invalid)}")
    if not mechanism or not normalized_claim_ids:
        normalized_horizons = {horizon: "UNKNOWN" for horizon in HORIZONS}

    direction_id = make_id(
        "direction",
        {
            "mapping_id": mapping["mapping_id"],
            "event_id": mapping["event_id"],
            "company_id": mapping["company_id"],
        },
    )
    return {
        "direction_id": direction_id,
        "mapping_id": mapping["mapping_id"],
        "event_id": mapping["event_id"],
        "company_id": mapping["company_id"],
        "anchor_id": mapping.get("anchor_id"),
        "binding_id": mapping.get("binding_id"),
        "horizons": normalized_horizons,
        "mechanism": mechanism,
        "conditions": list(conditions),
        "invalidation_conditions": list(invalidation_conditions),
        "claim_ids": normalized_claim_ids,
        "counterevidence_ids": [str(value) for value in counterevidence_ids],
        "evidence": evidence_rows,
        "confidence": confidence,
        "review_origin": "AI_DESK_REVIEW",
        "review_status": "NEEDS_HUMAN_REVIEW",
        "hidden_label_eligible": False,
        "price_selection_used": False,
        "formal_ready": False,
    }
