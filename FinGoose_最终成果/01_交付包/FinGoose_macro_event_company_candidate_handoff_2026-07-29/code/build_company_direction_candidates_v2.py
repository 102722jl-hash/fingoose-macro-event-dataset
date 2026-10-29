"""Build 30 event-company AI desk-review direction candidates."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from fingoose_company_impact_direction_v2 import build_direction


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def build(root: Path, output: Path | None = None) -> dict[str, Any]:
    config = root / "configs" / "company_impact_high_quality_v2"
    source_output = root / "work" / "company_impact_high_quality_v2_candidate"
    output = output or source_output
    mappings = read_jsonl(config / "event_company_map.jsonl")
    specs = read_jsonl(config / "direction_reviews.jsonl")
    claims = read_jsonl(source_output / "company_claim_candidates.jsonl")
    evidence = read_jsonl(source_output / "company_evidence.jsonl")

    mapping_by_pair = {
        (row["event_id"], row["company_code"]): row for row in mappings
    }
    spec_by_pair = {(row["event_id"], row["company_code"]): row for row in specs}
    if len(mapping_by_pair) != 30 or len(spec_by_pair) != 30:
        raise ValueError("DIRECTION_CARDINALITY_MISMATCH")
    if set(mapping_by_pair) != set(spec_by_pair):
        raise ValueError("DIRECTION_MAPPING_COVERAGE_MISMATCH")

    claims_by_company: dict[str, list[dict[str, Any]]] = defaultdict(list)
    evidence_by_company: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in claims:
        claims_by_company[str(row["company_id"])].append(row)
    for row in evidence:
        evidence_by_company[str(row["company_id"])].append(row)

    directions: list[dict[str, Any]] = []
    exposures: list[dict[str, Any]] = []
    for pair in sorted(mapping_by_pair):
        mapping = mapping_by_pair[pair]
        spec = spec_by_pair[pair]
        company_claims = claims_by_company[str(mapping["company_id"])]
        company_evidence = evidence_by_company[str(mapping["company_id"])]
        claim_ids = [str(row["claim_id"]) for row in company_claims]
        direction_evidence = [
            {
                "kind": "OFFICIAL_DISCLOSURE_CANDIDATE",
                "evidence_id": row["evidence_id"],
                "source_id": row["source_id"],
                "availability_scope": row["availability_scope"],
                "review_status": row["review_status"],
            }
            for row in company_evidence
        ]
        row = build_direction(
            mapping,
            horizons=spec["horizons"],
            mechanism=spec["mechanism"],
            claim_ids=claim_ids,
            evidence=direction_evidence,
            conditions=spec.get("conditions", []),
            invalidation_conditions=spec.get("invalidation_conditions", []),
            confidence=str(spec.get("confidence", "LOW")),
        )
        row.update(
            {
                "company_code": mapping["company_code"],
                "company_name": mapping["company_name"],
                "industry": mapping["industry"],
                "lineage_status": mapping["lineage_status"],
                "binding_selection_status": mapping[
                    "binding_selection_status"
                ],
                "candidate_binding_ids": mapping["candidate_binding_ids"],
                "sha_gate": "DEFERRED",
            }
        )
        directions.append(row)
        exposures.append(
            {
                "mapping_id": mapping["mapping_id"],
                "event_id": mapping["event_id"],
                "anchor_id": mapping["anchor_id"],
                "binding_id": mapping["binding_id"],
                "candidate_binding_ids": mapping["candidate_binding_ids"],
                "industry_impact_id": mapping["industry_impact_id"],
                "company_id": mapping["company_id"],
                "company_code": mapping["company_code"],
                "claim_ids": claim_ids,
                "evidence_ids": [
                    row["evidence_id"] for row in company_evidence
                ],
                "direction_id": row["direction_id"],
                "review_status": "NEEDS_HUMAN_REVIEW",
                "evaluation_eligible": False,
                "formal_ready": False,
            }
        )

    write_jsonl(output / "event_company_exposures.jsonl", exposures)
    write_jsonl(output / "direction_assessments.jsonl", directions)
    summary = {
        "direction_count": len(directions),
        "unknown_all_horizons_count": sum(
            set(row["horizons"].values()) == {"UNKNOWN"} for row in directions
        ),
        "needs_human_review_count": sum(
            row["review_status"] == "NEEDS_HUMAN_REVIEW" for row in directions
        ),
        "price_leakage_count": sum(
            evidence_row.get("kind") == "PRICE_OUTCOME"
            for row in directions
            for evidence_row in row["evidence"]
        ),
        "binding_confirmed_count": sum(
            row["binding_id"] is not None for row in directions
        ),
        "sha_gate": "DEFERRED",
        "formal_ready": False,
    }
    (output / "direction_candidate_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    print(json.dumps(build(project_root), ensure_ascii=False, indent=2))
