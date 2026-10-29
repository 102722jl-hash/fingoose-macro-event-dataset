"""Candidate-completion gates with confounder evidence-closure checks."""

from __future__ import annotations

from typing import Any, Mapping

from _fingoose_company_candidate_completion_v2_base import (
    DIRECTIONS,
    DOSSIER_CATEGORIES,
    HORIZONS,
    MECHANISM_NODE_TYPES,
    WINDOWS,
    build_binding_review,
    build_horizon_reviews,
)
from _fingoose_company_candidate_completion_v2_base import (
    evaluate_completion as _base_evaluate_completion,
)


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
    result = _base_evaluate_completion(
        mapping_id=mapping_id,
        binding_review=binding_review,
        dossier=dossier,
        direction=direction,
        market_window=market_window,
        relative_window=relative_window,
        confounder=confounder,
        mechanism_chain=mechanism_chain,
    )
    blockers = list(result["blockers"])
    if confounder.get("overall_grade") == "UNRESOLVED":
        blockers.append("CONFOUNDER_GRADE_UNRESOLVED")
    search_status = confounder.get("search_status")
    if search_status is not None and search_status != "COMPLETE":
        blockers.append("CONFOUNDER_SEARCH_INCOMPLETE")
    result["blockers"] = list(dict.fromkeys(blockers))
    result["completion_status"] = "CANDIDATE_COMPLETE" if not blockers else "OPEN"
    return result
