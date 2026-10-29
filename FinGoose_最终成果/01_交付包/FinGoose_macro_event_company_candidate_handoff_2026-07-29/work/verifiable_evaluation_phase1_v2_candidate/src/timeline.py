import argparse
import copy
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.evidence import validate_verified_node
from src.io_utils import read_jsonl, write_jsonl


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_ROOT.parents[1]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _precision(value: str) -> str:
    if len(value) == 10:
        return "DATE"
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return "MINUTE" if parsed.second == 0 and parsed.microsecond == 0 else "SECOND"


def _load_workbench_sources(events_path: Path) -> dict[str, dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {}
    for path in sorted(events_path.glob("event-*/sources.json")):
        for source in json.loads(path.read_text(encoding="utf-8-sig")):
            sources[source["source_id"]] = source
    return sources


def _time_evidence(
    source_id: str,
    locator: str,
    quote: str,
) -> dict[str, str]:
    return {"source_id": source_id, "locator": locator, "quote": quote}


def _evidence_from_source(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": source["source_id"],
        "publisher": source["publisher"],
        "source_tier": source["source_tier"],
        "url": source["url"],
        "quote": source["quote"],
        "locator": source["locator"],
        "snapshot_path": source.get("snapshot_path"),
        "sha256": source.get("sha256"),
    }


def _apply_resolution(
    baseline: dict[str, Any],
    resolution: dict[str, Any],
) -> dict[str, Any]:
    node = copy.deepcopy(baseline)
    original_id = node["fast_node_id"]
    source = resolution["source"]
    time_source = resolution.get("time_source")

    node["fast_node_id"] = resolution.get("new_fast_node_id", original_id)
    if resolution.get("supersedes_node_id"):
        node["supersedes_node_id"] = resolution["supersedes_node_id"]
    for field in ("fact", "phase", "node_action"):
        if field in resolution:
            node[field] = resolution[field]

    node["evidence_status"] = "VERIFIED_EXISTING"
    node["status"] = "PROPOSED"
    node["gap_reason"] = None
    evidence_sources = (
        [source]
        + resolution.get("supporting_sources", [])
        + ([time_source] if time_source else [])
    )
    node["source_ids"] = [item["source_id"] for item in evidence_sources]
    node["evidence"] = [_evidence_from_source(item) for item in evidence_sources]
    node["verification_basis"] = "PHASE1_EVIDENCE_RESOLUTION"

    occurred = resolution["occurred"]
    first_public = resolution["first_public"]
    node["occurred_at"] = occurred["value"]
    node["occurred_at_precision"] = occurred["precision"]
    node["occurred_at_evidence"] = _time_evidence(
        source["source_id"], occurred["locator"], occurred.get("quote", source["quote"])
    )
    node["first_public_at"] = first_public["value"]
    node["first_public_at_precision"] = first_public["precision"]
    first_public_source = time_source or source
    node["first_public_at_evidence"] = _time_evidence(
        first_public_source["source_id"],
        first_public["locator"],
        first_public.get("quote", first_public_source["quote"]),
    )

    semantic_change = bool(resolution.get("new_fast_node_id") or resolution.get("fact")) and (
        resolution.get("fact", baseline["fact"]) != baseline["fact"]
    )
    node["semantic_change"] = semantic_change
    if semantic_change:
        node["replacement_audit"] = {
            "original_fast_node_id": original_id,
            "original_fact": baseline["fact"],
            "original_source_ids": resolution.get(
                "original_source_ids", baseline.get("source_ids", [])
            ),
            "replacement_fast_node_id": node["fast_node_id"],
            "replacement_fact": node["fact"],
            "replacement_source_ids": node["source_ids"],
            "replacement_reason": resolution.get(
                "replacement_reason", "The source-aligned fact replaces an underspecified legacy label."
            ),
            "affected_records": resolution.get(
                "affected_records", ["timeline", "promotions", "anchor projection"]
            ),
            "review_result": "REVIEWED",
        }
    else:
        node.pop("replacement_audit", None)
    return node


def _apply_accepted_audit(
    baseline: dict[str, Any],
    audit: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    node = copy.deepcopy(baseline)
    source_id = manifest["candidate_source_id"]
    quote = audit["evidence_quote"]
    locator = audit["evidence_locator"]
    source = {
        "source_id": source_id,
        "publisher": manifest["publisher"],
        "source_tier": manifest["source_tier"],
        "url": manifest["source_url"],
        "quote": quote,
        "locator": locator,
        "snapshot_path": (
            f"work/timeline_fast_candidate_v2/{manifest['snapshot_path']}"
            if manifest.get("snapshot_path")
            else None
        ),
        "sha256": manifest.get("sha256"),
    }
    occurred = audit["occurred_at_verification"]
    first_public = audit["first_public_at_verification"]

    node["evidence_status"] = "VERIFIED_EXISTING"
    node["status"] = "PROPOSED"
    node["gap_reason"] = None
    node["source_ids"] = [source_id]
    node["evidence"] = [_evidence_from_source(source)]
    node["occurred_at"] = occurred["value"]
    node["occurred_at_precision"] = _precision(occurred["value"])
    node["occurred_at_evidence"] = _time_evidence(
        source_id, occurred["locator"], quote
    )
    node["first_public_at"] = first_public["value"]
    node["first_public_at_precision"] = _precision(first_public["value"])
    node["first_public_at_evidence"] = _time_evidence(
        source_id, first_public["locator"], quote
    )
    node["semantic_change"] = False
    node["verification_basis"] = "ACCEPTED_SUPPLEMENTAL_AUDIT"
    return node


def calculate_promotion(node: dict[str, Any]) -> bool:
    return all(
        (
            node.get("evidence_status") == "VERIFIED_EXISTING",
            not validate_verified_node(node),
            node.get("gap_reason") is None,
            node.get("anchor_role") in {"PRIMARY", "SECONDARY"},
            bool(node.get("original_milestone_id")),
            node.get("node_action") in {"STARTS", "AMPLIFIES", "WEAKENS"},
            node.get("visibility") == "PUBLIC_PREDICTION",
        )
    )


def build_timeline(
    baseline_path: Path,
    audit_path: Path,
    manifest_path: Path,
    workbench_events_path: Path,
    resolutions_path: Path,
) -> dict[str, list[dict[str, Any]]]:
    baseline = read_jsonl(baseline_path)
    audits = {row["attachment_node_id"]: row for row in read_jsonl(audit_path)}
    manifests = {row["attachment_node_id"]: row for row in read_jsonl(manifest_path)}
    resolutions = _read_json(resolutions_path)
    _load_workbench_sources(workbench_events_path)

    nodes: list[dict[str, Any]] = []
    for row in baseline:
        node_id = row["fast_node_id"]
        if node_id in resolutions:
            node = _apply_resolution(row, resolutions[node_id])
        else:
            audit = audits.get(node_id)
            manifest = manifests.get(node_id)
            if not audit or audit.get("decision") != "ACCEPTED" or not manifest:
                raise ValueError(f"{node_id}: no accepted audit or phase-1 resolution")
            node = _apply_accepted_audit(row, audit, manifest)
        errors = validate_verified_node(node)
        if errors:
            raise ValueError(f"{node['fast_node_id']}: {'; '.join(errors)}")
        nodes.append(node)

    ids = [node["fast_node_id"] for node in nodes]
    if len(nodes) != 50 or len(set(ids)) != 50:
        raise ValueError("timeline must contain exactly 50 unique node IDs")

    promotions = [
        {
            "fast_node_id": node["fast_node_id"],
            "event_id": node["event_id"],
            "original_milestone_id": node.get("original_milestone_id"),
            "promotion_basis": "PHASE1_RECOMPUTED",
            "evidence_status": node["evidence_status"],
        }
        for node in nodes
        if calculate_promotion(node)
    ]
    return {"nodes": nodes, "promotions": promotions}


def build_source_manifest(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    document_fields = (
        "publisher",
        "source_tier",
        "url",
        "snapshot_path",
        "sha256",
    )
    for node in nodes:
        for source in node["evidence"]:
            source_id = source["source_id"]
            excerpt = {
                "quote": source["quote"],
                "locator": source["locator"],
            }
            if source_id not in rows:
                row = copy.deepcopy(source)
                row["evidence_excerpts"] = [excerpt]
                rows[source_id] = row
                continue
            row = rows[source_id]
            if any(row.get(field) != source.get(field) for field in document_fields):
                raise ValueError(f"{source_id}: conflicting document-level source metadata")
            if excerpt not in row["evidence_excerpts"]:
                row["evidence_excerpts"].append(excerpt)
    for row in rows.values():
        row["evidence_excerpts"] = sorted(
            row["evidence_excerpts"],
            key=lambda item: (item["locator"], item["quote"]),
        )
    return [rows[source_id] for source_id in sorted(rows)]

def _build_outputs(output_dir: Path) -> dict[str, Any]:
    result = build_timeline(
        baseline_path=PROJECT_ROOT / "work" / "timeline_fast_candidate_v2" / "timeline_nodes.jsonl",
        audit_path=PROJECT_ROOT
        / "work"
        / "timeline_fast_candidate_v2"
        / "candidate_source_audit.jsonl",
        manifest_path=PROJECT_ROOT
        / "work"
        / "timeline_fast_candidate_v2"
        / "candidate_source_manifest.jsonl",
        workbench_events_path=PROJECT_ROOT / "work" / "ten_event_rapid_candidate_v2" / "events",
        resolutions_path=PACKAGE_ROOT / "config" / "evidence_resolutions.json",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "timeline_nodes.jsonl", result["nodes"])
    write_jsonl(output_dir / "promotable_milestones.jsonl", result["promotions"])

    replacements = [
        node["replacement_audit"] for node in result["nodes"] if node.get("semantic_change")
    ]
    write_jsonl(output_dir / "semantic_replacements.jsonl", replacements)

    write_jsonl(
        output_dir / "source_manifest.jsonl",
        build_source_manifest(result["nodes"]),
    )

    report = {
        "event_count": len({node["event_id"] for node in result["nodes"]}),
        "node_count": len(result["nodes"]),
        "verified_count": sum(
            node["evidence_status"] == "VERIFIED_EXISTING" for node in result["nodes"]
        ),
        "pending_evidence_count": sum(
            node["evidence_status"] == "PENDING_EVIDENCE" for node in result["nodes"]
        ),
        "semantic_replacement_count": len(replacements),
        "promotable_count": len(result["promotions"]),
        "hard_failures": [],
        "formal_ready": False,
        "sha_gate": "DEFERRED",
        "release_tier": "CANDIDATE",
    }
    (output_dir / "timeline_validation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()
    if args.build:
        report = _build_outputs(PACKAGE_ROOT)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
