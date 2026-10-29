"""Build candidate-completion layers for the frozen 30 event-company mappings."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from build_fingoose_company_mechanism_chains_v2 import (
    build as build_mechanism_chains,
)

from fingoose_company_candidate_completion_v2 import (
    build_binding_review,
    build_horizon_reviews,
    evaluate_completion,
)
from fingoose_company_impact_io_v2 import read_jsonl, write_jsonl
from fingoose_company_binding_selection_v2 import BINDING_SELECTIONS


EVENT_ORDER = (
    "event-04",
    "event-03",
    "event-09",
    "event-10",
    "event-02",
    "event-01",
    "event-07",
    "event-06",
    "event-05",
    "event-08",
)
BROAD_CHANNEL_EVENTS = {"event-01", "event-05", "event-09"}
CATEGORY_TO_CLAIM = {
    "BUSINESS_STRUCTURE": "BUSINESS_EXPOSURE",
    "GEOGRAPHIC_EXPOSURE": "GEOGRAPHIC_EXPOSURE",
    "DEMAND_SENSITIVITY": "DEMAND_COST_EXPOSURE",
    "COST_SENSITIVITY": "DEMAND_COST_EXPOSURE",
    "LIMITATIONS_AND_COUNTEREVIDENCE": "LIMITATION_OR_COUNTEREVIDENCE",
}
HORIZONS = ("IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _copy_rows(source: Path, destination: Path) -> list[dict[str, Any]]:
    rows = read_jsonl(source)
    write_jsonl(destination, rows)
    return rows


def _mapping_sort_key(row: Mapping[str, Any]) -> tuple[int, str]:
    return (EVENT_ORDER.index(str(row["event_id"])), str(row["mapping_id"]))


def _index_by(rows: Iterable[Mapping[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row[key]): dict(row) for row in rows}


def _claims_by_company(
    claims: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, dict[str, Any]]]:
    result: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for raw in claims:
        row = dict(raw)
        result[str(row["company_id"])][str(row["claim_type"])] = row
    return result


def _evidence_by_company(
    evidence: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in evidence:
        result[str(raw["company_id"])].append(dict(raw))
    return result


def _build_dossiers(
    dossiers: Sequence[Mapping[str, Any]],
    claims: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    claims_index = _claims_by_company(claims)
    enriched: list[dict[str, Any]] = []
    search_audits: list[dict[str, Any]] = []
    for raw in dossiers:
        dossier = dict(raw)
        company_id = str(dossier["company_id"])
        categories: list[dict[str, Any]] = []
        for category, claim_type in CATEGORY_TO_CLAIM.items():
            claim = claims_index.get(company_id, {}).get(claim_type, {})
            evidence_ids = list(claim.get("candidate_evidence_ids") or [])
            if evidence_ids:
                categories.append(
                    {
                        "category": category,
                        "claim_id": claim.get("claim_id"),
                        "status": "EVIDENCE_SUPPORTED",
                        "evidence_ids": evidence_ids,
                        "search_audit_ids": [],
                        "evidence_review_status": "NEEDS_HUMAN_REVIEW",
                    }
                )
                continue
            audit_id = "dossier-search-" + company_id + "-" + category.lower()
            search_audits.append(
                {
                    "search_audit_id": audit_id,
                    "company_id": company_id,
                    "company_code": dossier["company_code"],
                    "category": category,
                    "claim_id": claim.get("claim_id"),
                    "searched_source_ids": list(dossier.get("source_ids") or []),
                    "search_method": "OFFICIAL_REPORT_PAGE_EXTRACTION_KEYWORD_PROFILE",
                    "search_scope": "ANNUAL_AND_INTERIM_REPORTS_AVAILABLE_BEFORE_EVENT_CUTOFF",
                    "result": "NOT_DISCLOSED_AFTER_SEARCH",
                    "limitations": (
                        "\u672c\u7ed3\u8bba\u4ec5\u8868\u793a\u73b0\u6709\u5b98\u65b9\u62a5\u544a\u62bd\u53d6\u9875\u672a\u547d\u4e2d\u8be5\u9879\uff0c"
                        "\u4e0d\u7b49\u540c\u4e8e\u53d1\u884c\u4eba\u4ece\u672a\u62ab\u9732\u3002"
                    ),
                    "review_status": "NEEDS_HUMAN_REVIEW",
                    "formal_ready": False,
                    "sha_gate": "DEFERRED",
                }
            )
            categories.append(
                {
                    "category": category,
                    "claim_id": claim.get("claim_id"),
                    "status": "NOT_DISCLOSED_AFTER_SEARCH",
                    "evidence_ids": [],
                    "search_audit_ids": [audit_id],
                    "evidence_review_status": "NEEDS_HUMAN_REVIEW",
                }
            )
        dossier.update(
            {
                "research_categories": categories,
                "dossier_status": "EVIDENCE_COMPLETE_CANDIDATE",
                "gap_reason": None,
                "review_status": "NEEDS_HUMAN_REVIEW",
                "formal_ready": False,
                "sha_gate": "DEFERRED",
            }
        )
        enriched.append(dossier)
    return enriched, search_audits


def _edge_rejection_reason(edge: Mapping[str, Any]) -> str:
    from_id = str(edge.get("from_node_id") or "")
    to_id = str(edge.get("to_node_id") or "")
    if "-intermediate-" in from_id or "-asset-" in to_id:
        return "DOWNSTREAM_MARKET_PROJECTION_NOT_SELECTED_FOR_COMPANY_MECHANISM"
    return "LOWER_PRIORITY_OR_NON_COMPANY_CHANNEL_FOR_THIS_MAPPING"


def _build_binding_reviews(
    mappings: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    directions: Sequence[Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    edges_by_id = _index_by(edges, "binding_id")
    directions_by_mapping = _index_by(directions, "mapping_id")
    evidence_index = _evidence_by_company(evidence)
    reviews: list[dict[str, Any]] = []
    for mapping in sorted(mappings, key=_mapping_sort_key):
        event_id = str(mapping["event_id"])
        primary, secondary = BINDING_SELECTIONS[event_id]
        candidates = [str(value) for value in mapping.get("candidate_binding_ids") or []]
        if primary not in candidates or any(value not in candidates for value in secondary):
            raise ValueError("CONFIGURED_BINDING_NOT_IN_MAPPING:" + str(mapping["mapping_id"]))
        company_evidence = evidence_index[str(mapping["company_id"])]
        evidence_ids = [str(row["evidence_id"]) for row in company_evidence]
        counterevidence_ids = [
            str(row["evidence_id"])
            for row in company_evidence
            if row.get("claim_type") == "LIMITATION_OR_COUNTEREVIDENCE"
        ]
        event_evidence_ids = sorted(
            {
                str(item["evidence_id"])
                for binding_id in (primary, *secondary)
                for item in edges_by_id[binding_id].get("mechanism_evidence") or []
            }
        )
        selected = {primary, *secondary}
        rejected = {
            binding_id: _edge_rejection_reason(edges_by_id[binding_id])
            for binding_id in candidates
            if binding_id not in selected
        }
        mechanism = str(directions_by_mapping[str(mapping["mapping_id"])].get("mechanism") or "")
        selection_basis = (
            mechanism
            + " \u4e3b\u8fb9\u4f9d\u636e\u4e8b\u4ef6\u951a\u70b9\u4e0e\u4e8b\u4ef6\u524d\u53ef\u89c1\u7684\u516c\u53f8\u5b98\u65b9\u4e1a\u52a1\u62ab\u9732\u9009\u62e9\uff0c"
            "\u672a\u4f7f\u7528\u4e8b\u540e\u80a1\u4ef7\u3002"
        ).strip()
        review = build_binding_review(
            mapping,
            primary_binding_id=primary,
            secondary_binding_ids=secondary,
            rejected_bindings=rejected,
            selection_basis=selection_basis,
            evidence_ids=event_evidence_ids + evidence_ids,
            counterevidence_ids=counterevidence_ids,
        )
        review.update(
            {
                "company_id": mapping["company_id"],
                "company_code": mapping["company_code"],
                "company_name": mapping["company_name"],
                "industry_impact_id": mapping["industry_impact_id"],
                "event_evidence_ids": event_evidence_ids,
                "company_evidence_ids": evidence_ids,
                "semantic_alignment_status": (
                    "BROAD_CHANNEL_ONLY"
                    if event_id in BROAD_CHANNEL_EVENTS
                    else "COMPANY_MECHANISM_CANDIDATE"
                ),
                "selected_binding_lineage": [
                    {
                        "binding_id": binding_id,
                        "from_node_id": edges_by_id[binding_id].get("from_node_id"),
                        "to_node_id": edges_by_id[binding_id].get("to_node_id"),
                        "binding_status": edges_by_id[binding_id].get("binding_status"),
                    }
                    for binding_id in (primary, *secondary)
                ],
                "sha_gate": "DEFERRED",
            }
        )
        reviews.append(review)
    return reviews


def _build_direction_reviews(
    directions: Sequence[Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    evidence_index = _evidence_by_company(evidence)
    enriched: list[dict[str, Any]] = []
    for raw in directions:
        row = dict(raw)
        company_evidence = evidence_index[str(row["company_id"])]
        evidence_ids = [str(item["evidence_id"]) for item in company_evidence]
        counterevidence_ids = [
            str(item["evidence_id"])
            for item in company_evidence
            if item.get("claim_type") == "LIMITATION_OR_COUNTEREVIDENCE"
        ]
        abstentions = {
            horizon: {
                "reason": (
                    "\u73b0\u6709\u4e8b\u4ef6\u524d\u516c\u53f8\u62ab\u9732\u65e0\u6cd5\u652f\u6301\u8be5\u671f\u9650\u7684\u5355\u5411\u5224\u65ad\u3002"
                ),
                "missing_evidence": [
                    "COMPANY_SPECIFIC_HORIZON_MECHANISM",
                    "COMPETING_MECHANISM_RANKING",
                ],
            }
            for horizon in HORIZONS
            if row.get("horizons", {}).get(horizon) == "UNKNOWN"
        }
        row.update(
            {
                "horizon_reviews": build_horizon_reviews(
                    row["horizons"],
                    abstentions=abstentions,
                    conditions=row.get("conditions") or [],
                    invalidation_conditions=row.get("invalidation_conditions") or [],
                    evidence_ids=evidence_ids,
                    counterevidence_ids=counterevidence_ids,
                ),
                "review_status": "NEEDS_HUMAN_REVIEW",
                "formal_ready": False,
                "sha_gate": "DEFERRED",
            }
        )
        enriched.append(row)
    return enriched


def _build_industry_registry(
    mappings: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for mapping in mappings:
        classification = mapping.get("industry_classification") or {}
        grouped[str(classification.get("sw1_id"))].append(mapping)
    registry: list[dict[str, Any]] = []
    for industry_id, rows in sorted(grouped.items()):
        classifications = [row.get("industry_classification") or {} for row in rows]
        first = classifications[0]
        dates = sorted(
            str(item.get("event_as_of_date"))
            for item in classifications
            if item.get("event_as_of_date")
        )
        registry.append(
            {
                "industry_id": industry_id,
                "industry_name": first.get("sw1_name"),
                "benchmark_id": "SW1-" + industry_id,
                "benchmark_code": industry_id + ".SI",
                "benchmark_type": "SHENWAN_L1_INDEX",
                "valid_from": dates[0] if dates else None,
                "valid_to_exclusive": None,
                "selection_basis": (
                    "\u6309\u4e8b\u4ef6\u65e5\u751f\u6548\u7684\u7533\u4e07\u4e00\u7ea7\u884c\u4e1a\u5206\u7c7b\u9884\u5148\u6307\u5b9a\uff1b"
                    "\u672a\u4f7f\u7528\u4e8b\u540e\u884c\u60c5\u6311\u9009\u57fa\u51c6\u3002"
                ),
                "source": {
                    "publisher": "SHENWAN_HONGYUAN_RESEARCH",
                    "title": "SHENWAN_INDEX_RELEASED_INDEX",
                    "url": "https://www.swsresearch.com/institute_sw/allIndex/releasedIndex",
                },
                "licence_status": "UNKNOWN_CANDIDATE_RESEARCH_ONLY",
                "history_data_status": "DATA_PENDING",
                "fallback_etf_status": "NOT_SELECTED_WITHOUT_PRE_EVENT_LISTING_EVIDENCE",
                "review_status": "NEEDS_HUMAN_REVIEW",
                "formal_ready": False,
                "sha_gate": "DEFERRED",
            }
        )
    return registry


def build(root: Path, output: Path) -> dict[str, Any]:
    root = root.resolve()
    output = output.resolve()
    source = root / "work/company_impact_high_quality_v2_candidate"
    output.mkdir(parents=True, exist_ok=True)

    mappings = read_jsonl(source / "event_company_map.jsonl")
    claims = read_jsonl(source / "company_claim_candidates.jsonl")
    evidence = read_jsonl(source / "company_evidence.jsonl")
    dossiers = read_jsonl(source / "company_master_dossiers.jsonl")
    directions = read_jsonl(source / "direction_assessments.jsonl")
    market_windows = read_jsonl(source / "company_market_windows.jsonl")
    relative_windows = read_jsonl(source / "relative_return_windows.jsonl")
    confounders = read_jsonl(source / "company_confounders.jsonl")
    edges = read_jsonl(
        root / "work/transmission_24_anchor_v2_candidate/dynamic_edge_bindings.jsonl"
    )

    if len(mappings) != 30 or len({row["mapping_id"] for row in mappings}) != 30:
        raise ValueError("FROZEN_MAPPING_CARDINALITY_MISMATCH")

    enriched_dossiers, search_audits = _build_dossiers(dossiers, claims)
    enriched_directions = _build_direction_reviews(directions, evidence)
    binding_reviews = _build_binding_reviews(mappings, edges, enriched_directions, evidence)
    industry_registry = _build_industry_registry(mappings)
    write_jsonl(output / "event_company_binding_reviews.jsonl", binding_reviews)
    write_jsonl(output / "company_dossier_search_audits.jsonl", search_audits)
    write_jsonl(output / "company_master_dossiers.jsonl", enriched_dossiers)
    write_jsonl(output / "direction_assessments.jsonl", enriched_directions)
    write_jsonl(output / "industry_benchmark_registry.jsonl", industry_registry)
    for name, rows in (
        ("company_market_windows.jsonl", market_windows),
        ("relative_return_windows.jsonl", relative_windows),
        ("company_confounders.jsonl", confounders),
    ):
        write_jsonl(output / name, rows)

    mechanism_summary = build_mechanism_chains(root, output=output)
    mechanism_chains = read_jsonl(output / "event_company_mechanism_chains.jsonl")

    dossiers_by_company = _index_by(enriched_dossiers, "company_id")
    directions_by_mapping = _index_by(enriched_directions, "mapping_id")
    bindings_by_mapping = _index_by(binding_reviews, "mapping_id")
    markets_by_mapping = _index_by(market_windows, "mapping_id")
    relatives_by_mapping = _index_by(relative_windows, "mapping_id")
    confounders_by_mapping = _index_by(confounders, "mapping_id")
    chains_by_mapping = _index_by(mechanism_chains, "mapping_id")
    completion = [
        evaluate_completion(
            mapping_id=str(mapping["mapping_id"]),
            mechanism_chain=chains_by_mapping[str(mapping["mapping_id"])],
            binding_review=bindings_by_mapping[str(mapping["mapping_id"])],
            dossier=dossiers_by_company[str(mapping["company_id"])],
            direction=directions_by_mapping[str(mapping["mapping_id"])],
            market_window=markets_by_mapping[str(mapping["mapping_id"])],
            relative_window=relatives_by_mapping[str(mapping["mapping_id"])],
            confounder=confounders_by_mapping[str(mapping["mapping_id"])],
        )
        for mapping in sorted(mappings, key=_mapping_sort_key)
    ]
    for row in completion:
        row["sha_gate"] = "DEFERRED"

    write_jsonl(output / "event_company_binding_reviews.jsonl", binding_reviews)
    write_jsonl(output / "company_dossier_search_audits.jsonl", search_audits)
    write_jsonl(output / "company_master_dossiers.jsonl", enriched_dossiers)
    write_jsonl(output / "direction_assessments.jsonl", enriched_directions)
    write_jsonl(output / "industry_benchmark_registry.jsonl", industry_registry)
    write_jsonl(output / "candidate_completion_report.jsonl", completion)
    for name, rows in (
        ("company_market_windows.jsonl", market_windows),
        ("relative_return_windows.jsonl", relative_windows),
        ("company_confounders.jsonl", confounders),
    ):
        write_jsonl(output / name, rows)

    report = {
        "mapping_count": len(mappings),
        "binding_review_count": len(binding_reviews),
        "mechanism_chain_count": mechanism_summary["chain_count"],
        "mechanism_chain_node_count": mechanism_summary["node_count"],
        "mechanism_chain_edge_count": mechanism_summary["edge_count"],
        "broad_channel_only_count": sum(
            row["semantic_alignment_status"] == "BROAD_CHANNEL_ONLY"
            for row in binding_reviews
        ),
        "dossier_count": len(enriched_dossiers),
        "dossier_search_audit_count": len(search_audits),
        "direction_horizon_review_count": len(enriched_directions),
        "explicit_abstention_count": sum(
            review["decision_status"] == "ABSTAIN"
            for row in enriched_directions
            for review in row["horizon_reviews"].values()
        ),
        "industry_benchmark_count": len(industry_registry),
        "industry_history_available_count": sum(
            row["history_data_status"] == "AVAILABLE" for row in industry_registry
        ),
        "completion_report_count": len(completion),
        "candidate_complete_count": sum(
            row["completion_status"] == "CANDIDATE_COMPLETE" for row in completion
        ),
        "open_count": sum(row["completion_status"] == "OPEN" for row in completion),
        "review_status": "NEEDS_HUMAN_REVIEW",
        "formal_ready": False,
        "sha_gate": "DEFERRED",
    }
    _write_json(output / "candidate_completion_summary.json", report)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("work/company_impact_high_quality_v2_candidate"),
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    print(json.dumps(build(root, output), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

