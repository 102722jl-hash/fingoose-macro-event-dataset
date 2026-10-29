"""Join fixed event anchors to industry and company candidate support data."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


DATASET_VERSION = "fingoose-event-industry-impact-v1.0"
RELEASE_TIER = "CANDIDATE"
FINANCIAL_STATEMENTS = ("BALANCE_SHEET", "INCOME_STATEMENT", "CASH_FLOW")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _financial_status(row: Mapping[str, Any]) -> str:
    statuses = [str((row.get(name) or {}).get("status", "UNKNOWN")) for name in FINANCIAL_STATEMENTS]
    if "PRE_EVENT_DATA_AVAILABLE" in statuses:
        return "PRE_EVENT_DATA_AVAILABLE"
    if "ANCHOR_UNKNOWN" in statuses:
        return "ANCHOR_UNKNOWN"
    return "NO_PRE_EVENT_DATA"


def _unique_strings(edges: Sequence[Mapping[str, Any]], field: str) -> list[str]:
    values = set()
    for edge in edges:
        for value in edge.get(field) or []:
            if value:
                values.add(str(value))
    return sorted(values)


def build_event_industry_candidates(
    anchors: Sequence[Mapping[str, Any]],
    graphs: Sequence[Mapping[str, Any]],
    companies: Sequence[Mapping[str, Any]],
    ratings: Sequence[Mapping[str, Any]],
    financials: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    graph_by_event = {str(row["event_id"]): row for row in graphs}
    companies_by_event: dict[str, list[Mapping[str, Any]]] = {}
    for row in companies:
        companies_by_event.setdefault(str(row["event_id"]), []).append(row)
    rating_by_key = {(str(row["event_id"]), str(row["company_code"])): row for row in ratings}
    financial_by_key = {(str(row["event_id"]), str(row["company_code"])): row for row in financials}
    output = []

    for anchor in sorted(anchors, key=lambda row: (str(row["event_id"]), int(row.get("sequence") or 0), str(row["anchor_id"]))):
        event_id = str(anchor["event_id"])
        graph = graph_by_event.get(event_id, {})
        node_by_id = {str(node["node_id"]): node for node in graph.get("nodes") or []}
        anchored_edges = [
            dict(edge) for edge in graph.get("edges") or []
            if str(edge.get("anchor_milestone_id")) == str(anchor.get("milestone_id"))
            and edge.get("status") == "PROPOSED"
        ]
        if anchor.get("activation_mode") != "CAUSAL_CANDIDATE":
            anchored_edges = []
        channels = sorted({
            str(node_by_id[node_id]["label"])
            for edge in anchored_edges
            for node_id in (str(edge.get("from_node_id")), str(edge.get("to_node_id")))
            if node_id in node_by_id and node_by_id[node_id].get("layer") == "channel"
        })
        grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
        for company in companies_by_event.get(event_id, []):
            industry = str(company.get("industry") or "UNKNOWN")
            industry_status = str(company.get("industry_status") or "UNKNOWN")
            grouped.setdefault((industry, industry_status), []).append(company)

        for (industry, industry_status), industry_companies in sorted(grouped.items()):
            company_rows = []
            for company in sorted(industry_companies, key=lambda row: str(row["company_code"])):
                key = (event_id, str(company["company_code"]))
                rating = rating_by_key.get(key, {})
                financial = financial_by_key.get(key, {})
                company_rows.append({
                    "company_code": company["company_code"],
                    "company_name": company["company_name"],
                    "rating_support_status": rating.get("status", "UNKNOWN"),
                    "rating_window_id": rating.get("rating_window_id"),
                    "financial_support_status": _financial_status(financial),
                    "financial_baseline_id": financial.get("financial_baseline_id"),
                    "official_company_exposure_verified": False,
                })
            slug = industry.lower().replace(" ", "-").replace("/", "-") or "unknown"
            output.append({
                "impact_candidate_id": f"event-industry-{anchor['anchor_id']}-{slug}",
                "dataset_version": DATASET_VERSION,
                "release_tier": RELEASE_TIER,
                "event_id": event_id,
                "anchor_id": anchor["anchor_id"],
                "anchor_milestone_id": anchor.get("milestone_id"),
                "anchor_fact": anchor.get("fact"),
                "anchor_evidence_status": anchor.get("evidence_status"),
                "activation_mode": anchor.get("activation_mode"),
                "impact_labels": list(anchor.get("impact_tags") or []),
                "graph_id": graph.get("graph_id"),
                "channels": channels,
                "transmission_edges": [
                    {
                        "edge_id": edge.get("edge_id"),
                        "from_node_id": edge.get("from_node_id"),
                        "to_node_id": edge.get("to_node_id"),
                        "expected_path": edge.get("expected_path"),
                        "status": edge.get("status"),
                        "confidence": edge.get("confidence"),
                    }
                    for edge in anchored_edges
                ],
                "conditions": _unique_strings(anchored_edges, "conditions"),
                "invalidation_conditions": _unique_strings(anchored_edges, "invalidation_conditions"),
                "counterevidence": _unique_strings(anchored_edges, "counterevidence"),
                "industry": industry,
                "industry_status": industry_status,
                "companies": company_rows,
                "direction_status": "PROPOSED_CONDITIONAL" if anchored_edges else "UNKNOWN",
                "expected_industry_direction": "UNKNOWN",
                "official_company_exposure_verified": False,
                "causal_attribution_allowed": False,
                "post_event_price_used_for_direction": False,
                "formal_ready": False,
            })
    return output


def write_event_industry_bundle(output_root: Path, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    ordered = sorted((dict(row) for row in rows), key=lambda row: row["impact_candidate_id"])
    _write_jsonl(output_root / "event_industry_impact_candidates.jsonl", ordered)
    hard_failures = []
    ids = [row["impact_candidate_id"] for row in ordered]
    if len(ids) != len(set(ids)):
        hard_failures.append("DUPLICATE_IMPACT_CANDIDATE_ID")
    allowed_direction = {"PROPOSED_CONDITIONAL", "UNKNOWN"}
    for row in ordered:
        if row.get("direction_status") not in allowed_direction:
            hard_failures.append(f"INVALID_DIRECTION_STATUS:{row['impact_candidate_id']}")
        if row.get("expected_industry_direction") != "UNKNOWN":
            hard_failures.append(f"UNSUPPORTED_INDUSTRY_DIRECTION:{row['impact_candidate_id']}")
        if row.get("official_company_exposure_verified") or row.get("causal_attribution_allowed"):
            hard_failures.append(f"RELEASE_BOUNDARY_VIOLATION:{row['impact_candidate_id']}")
    validation = {
        "valid": not hard_failures,
        "hard_failures": hard_failures,
        "record_count": len(ordered),
        "event_count": len({row["event_id"] for row in ordered}),
        "anchor_count": len({row["anchor_id"] for row in ordered}),
        "company_association_count": sum(len(row["companies"]) for row in ordered),
        "conditional_count": sum(row["direction_status"] == "PROPOSED_CONDITIONAL" for row in ordered),
        "unknown_direction_count": sum(row["direction_status"] == "UNKNOWN" for row in ordered),
        "formal_ready": False,
    }
    summary = {
        "dataset_version": DATASET_VERSION,
        "release_tier": RELEASE_TIER,
        **{key: validation[key] for key in ("record_count", "event_count", "anchor_count", "company_association_count", "conditional_count", "unknown_direction_count")},
        "formal_ready": False,
        "official_company_exposure_verified": False,
        "causal_attribution_allowed": False,
    }
    _write_json(output_root / "validation_report.json", validation)
    _write_json(output_root / "summary.json", summary)
    (output_root / "README.md").write_text(
        "# Event Industry Impact Candidate\n\n"
        "This bundle joins fixed event anchors and proposed transmission edges to candidate industry/company associations. "
        "Industry direction remains unknown; ratings and financials are support context only.\n",
        encoding="utf-8",
    )
    files = [output_root / "event_industry_impact_candidates.jsonl", output_root / "validation_report.json", output_root / "summary.json", output_root / "README.md"]
    manifest = {
        "dataset_version": DATASET_VERSION,
        "release_tier": RELEASE_TIER,
        "formal_ready": False,
        "files": [
            {
                "path": path.name,
                "record_count": sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip()) if path.suffix == ".jsonl" else 1,
                "sha256": _sha256(path),
            }
            for path in files
        ],
    }
    _write_json(output_root / "manifest.json", manifest)
    return manifest


def build_event_industry_bundle(root: Path, output_root: Path) -> dict[str, Any]:
    root = root.resolve()
    output_root = output_root.resolve()
    protected = [(root / name).resolve() for name in ("data", "code", "ui")]
    if any(output_root == path or path in output_root.parents for path in protected):
        raise ValueError("output_root must remain outside protected production and UI directories")
    rows = build_event_industry_candidates(
        _read_jsonl(root / "work/transmission_24_anchor_v2_candidate/anchor_catalog.jsonl"),
        _read_jsonl(root / "work/transmission_24_anchor_v2_candidate/transmission_graphs.jsonl"),
        _read_jsonl(root / "work/mysql_company_enhancement_v1_candidate/company_impact_candidates.jsonl"),
        _read_jsonl(root / "work/mysql_company_enhancement_v1_candidate/company_rating_windows.jsonl"),
        _read_jsonl(root / "work/mysql_company_enhancement_v1_candidate/company_financial_baselines.jsonl"),
    )
    manifest = write_event_industry_bundle(output_root, rows)
    return {
        "record_count": len(rows),
        "anchor_count": len({row["anchor_id"] for row in rows}),
        "event_count": len({row["event_id"] for row in rows}),
        "manifest_file_count": len(manifest["files"]),
        "formal_ready": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("work/event_industry_impact_v1_candidate"))
    args = parser.parse_args(argv)
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    print(json.dumps(build_event_industry_bundle(root, output), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
