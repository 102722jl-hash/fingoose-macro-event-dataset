"""Freeze company identities and upstream event lineage for company-impact v2."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from fingoose_company_impact_io_v2 import make_id, write_jsonl


def _company_id(company_code: str) -> str:
    return make_id("company", {"company_code": company_code.upper()})


def _impact_rank(
    impact: Mapping[str, Any],
    anchors_by_id: Mapping[str, Mapping[str, Any]],
) -> tuple[int, int, int, str]:
    anchor = anchors_by_id.get(str(impact.get("anchor_id")), {})
    role_rank = {"PRIMARY": 0, "SECONDARY": 1}.get(
        str(anchor.get("anchor_role")),
        2,
    )
    return (
        0 if impact.get("lineage_status") == "GRAPH_LINKED_CANDIDATE" else 1,
        0 if impact.get("binding_ids") else 1,
        role_rank,
        str(impact.get("anchor_id")),
    )


def build_registry_and_map(
    candidates: Iterable[Mapping[str, Any]],
    impacts: Iterable[Mapping[str, Any]],
    anchors: Iterable[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidate_rows = [dict(row) for row in candidates]
    impact_rows = [dict(row) for row in impacts]
    anchors_by_id = {str(row["anchor_id"]): dict(row) for row in anchors}

    impacts_by_pair: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for impact in impact_rows:
        event_id = str(impact["event_id"])
        for company in impact.get("companies", []):
            impacts_by_pair[(event_id, str(company["company_code"]))].append(impact)

    companies_by_id: dict[str, dict[str, Any]] = {}
    mappings: list[dict[str, Any]] = []
    for candidate in candidate_rows:
        event_id = str(candidate["event_id"])
        company_code = str(candidate["company_code"]).upper()
        company_name = str(candidate["company_name"])
        company_id = _company_id(company_code)
        exchange = company_code.rsplit(".", 1)[-1]
        companies_by_id.setdefault(
            company_id,
            {
                "company_id": company_id,
                "company_code": company_code,
                "company_name": company_name,
                "exchange": exchange,
                "dossier_status": "DATA_PENDING",
                "formal_ready": False,
            },
        )

        matches = impacts_by_pair.get((event_id, company_code), [])
        if not matches:
            raise ValueError(f"MISSING_INDUSTRY_IMPACT:{event_id}:{company_code}")
        selected = sorted(
            matches,
            key=lambda row: _impact_rank(row, anchors_by_id),
        )[0]
        anchor_id = str(selected["anchor_id"])
        anchor = anchors_by_id.get(anchor_id)
        if anchor is None:
            raise ValueError(f"MISSING_ANCHOR:{event_id}:{anchor_id}")
        if str(anchor["event_id"]) != event_id:
            raise ValueError(f"CROSS_EVENT_ANCHOR:{event_id}:{anchor_id}")

        impact_id = str(selected["impact_candidate_id"])
        mapping_id = make_id(
            "event-company",
            {
                "event_id": event_id,
                "company_id": company_id,
                "industry_impact_id": impact_id,
            },
        )
        mappings.append(
            {
                "mapping_id": mapping_id,
                "event_id": event_id,
                "company_id": company_id,
                "company_code": company_code,
                "company_name": company_name,
                "anchor_id": anchor_id,
                "event_node_id": selected.get("event_node_id"),
                "industry_impact_id": impact_id,
                "industry": selected.get("industry"),
                "industry_classification": selected.get("industry_classification"),
                "lineage_status": selected.get("lineage_status"),
                "candidate_binding_ids": sorted(
                    str(value) for value in selected.get("binding_ids", [])
                ),
                "binding_id": None,
                "binding_selection_status": "PENDING_COMPANY_MECHANISM_REVIEW",
                "selection_cutoff_at": anchor.get("first_public_at"),
                "price_selection_used": False,
                "evaluation_eligible": False,
                "formal_ready": False,
            }
        )

    companies = sorted(
        companies_by_id.values(),
        key=lambda row: str(row["company_code"]),
    )
    mappings.sort(key=lambda row: (str(row["event_id"]), str(row["company_code"])))
    return companies, mappings


def write_registry_and_map(
    candidates: Iterable[Mapping[str, Any]],
    impacts: Iterable[Mapping[str, Any]],
    anchors: Iterable[Mapping[str, Any]],
    output_root: Path,
) -> dict[str, int]:
    companies, mappings = build_registry_and_map(
        candidates,
        impacts,
        anchors,
    )
    write_jsonl(output_root / "company_registry.jsonl", companies)
    write_jsonl(output_root / "event_company_map.jsonl", mappings)
    return {
        "company_count": len(companies),
        "mapping_count": len(mappings),
    }
