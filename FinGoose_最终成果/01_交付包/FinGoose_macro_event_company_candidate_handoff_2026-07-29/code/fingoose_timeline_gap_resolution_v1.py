"""Read-only audit for the eight unresolved FAST_CANDIDATE timeline nodes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


DATASET_VERSION = "fingoose-timeline-gap-resolution-v1.0"
RELEASE_TIER = "FAST_CANDIDATE_AUDIT"
GAP_NODE_IDS = (
    "fast-event-02-M01",
    "fast-event-05-M01",
    "fast-event-05-M04",
    "fast-event-06-M01",
    "fast-event-07-M05",
    "fast-event-10-M01",
    "fast-event-10-M04",
    "fast-event-10-M05",
)

KNOWN_BLOCKER_OVERRIDES = {
    "fast-event-02-M01": ["SEMANTIC_MISMATCH"],
    "fast-event-05-M01": ["CLAIMED_FIRST_PUBLIC_AT_NOT_IN_SNAPSHOT"],
    "fast-event-05-M04": ["TIMEZONE_NOT_PROVEN_BY_SNAPSHOT"],
    "fast-event-06-M01": ["EXACT_TIME_NOT_IN_SNAPSHOT"],
    "fast-event-07-M05": ["OFFICIAL_SNAPSHOT_MISSING"],
    "fast-event-10-M01": ["CLAIMED_TIME_CONTRADICTS_SNAPSHOT"],
    "fast-event-10-M04": ["FIRST_PUBLIC_TIME_NOT_IN_SNAPSHOT"],
    "fast-event-10-M05": ["FIRST_PUBLIC_TIME_NOT_IN_SNAPSHOT"],
}

NEXT_EVIDENCE_REQUIRED = {
    "fast-event-02-M01": "Find an EIA or equivalent first-party snapshot matching the low-inventory/geopolitical precondition, with independent occurred and first-public timestamps.",
    "fast-event-05-M01": "Obtain SEC accession metadata or an issuer release that independently proves the exact occurrence and first-public timestamps for the March 8 disclosure.",
    "fast-event-05-M04": "Obtain a FINMA or Swiss government timestamp carrying an explicit timezone for both the decision and first publication.",
    "fast-event-06-M01": "Obtain IEA release metadata with an exact publication time; the current snapshot proves only the publication date and oil-market fact.",
    "fast-event-07-M05": "Archive the identified GovInfo first-party PDF, hash it, and locate independent occurrence and first-public timestamps.",
    "fast-event-10-M01": "Replace the conflicting 2024 claim with a timestamped January 20, 2025 White House memorandum record.",
    "fast-event-10-M04": "Add an official publication-log timestamp for EO 14257/Annex I in addition to the effective-time clause.",
    "fast-event-10-M05": "Add an official publication-log timestamp for EO 14266 in addition to the signed-date and modification text.",
}

_AUTO = object()


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


def select_gap_nodes(nodes: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(row.get("fast_node_id")): dict(row) for row in nodes}
    missing = [node_id for node_id in GAP_NODE_IDS if node_id not in by_id]
    if missing:
        raise ValueError(f"missing fixed gap nodes: {missing}")
    selected = [by_id[node_id] for node_id in GAP_NODE_IDS]
    unexpected = [row["fast_node_id"] for row in selected if row.get("evidence_status") != "PENDING_EVIDENCE"]
    if unexpected:
        raise ValueError(f"fixed gap nodes are no longer pending: {unexpected}")
    return selected


def _verified_time(value: Any) -> bool:
    return bool(
        isinstance(value, Mapping)
        and value.get("status") == "VERIFIED"
        and value.get("value")
        and value.get("locator")
    )


def evaluate_gap_candidate(
    node: Mapping[str, Any],
    audit: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
    snapshot_root: Path,
    blocker_override: Any = _AUTO,
) -> dict[str, Any]:
    node_id = str(node["fast_node_id"])
    overrides = KNOWN_BLOCKER_OVERRIDES.get(node_id, []) if blocker_override is _AUTO else list(blocker_override or [])
    snapshot_path = source_manifest.get("snapshot_path") or audit.get("snapshot_path")
    snapshot = snapshot_root / str(snapshot_path) if snapshot_path else None
    snapshot_exists = bool(snapshot and snapshot.is_file())
    declared_sha = source_manifest.get("sha256") or audit.get("sha256")
    actual_sha = _sha256(snapshot) if snapshot_exists else None
    hash_match = bool(snapshot_exists and declared_sha and actual_sha == declared_sha)
    evidence_quote = audit.get("evidence_quote")
    quote_present = False
    if snapshot_exists and evidence_quote:
        try:
            quote_present = str(evidence_quote).casefold() in snapshot.read_text(encoding="utf-8", errors="ignore").casefold()
        except OSError:
            quote_present = False
    if "SEMANTIC_MISMATCH" in overrides:
        semantic_status = "SEMANTIC_MISMATCH"
    elif audit.get("fact_status") == "VERIFIED" and quote_present:
        semantic_status = "VERIFIED"
    elif quote_present:
        semantic_status = "FACT_TEXT_LOCATED"
    else:
        semantic_status = "UNVERIFIED"

    occurred = audit.get("occurred_at_verification") or {}
    first_public = audit.get("first_public_at_verification") or {}
    occurred_accepted = _verified_time(occurred)
    first_public_accepted = _verified_time(first_public)
    blockers = []
    if not snapshot_exists:
        blockers.append("SNAPSHOT_MISSING")
    elif not hash_match:
        blockers.append("SNAPSHOT_HASH_MISMATCH")
    if not audit.get("evidence_locator"):
        blockers.append("EVIDENCE_LOCATOR_MISSING")
    if semantic_status != "VERIFIED":
        blockers.append("SEMANTIC_FACT_NOT_VERIFIED")
    if not occurred_accepted:
        blockers.append("INDEPENDENT_OCCURRED_AT_NOT_VERIFIED")
    if not first_public_accepted:
        blockers.append("INDEPENDENT_FIRST_PUBLIC_AT_NOT_VERIFIED")
    if audit.get("decision") != "ACCEPTED":
        blockers.append("SOURCE_DECISION_NOT_ACCEPTED")
    blockers.extend(overrides)
    blockers = list(dict.fromkeys(blockers))
    promotion_eligible = not blockers
    return {
        "gap_resolution_id": f"gap-{node_id}",
        "dataset_version": DATASET_VERSION,
        "release_tier": RELEASE_TIER,
        "fast_node_id": node_id,
        "event_id": node.get("event_id"),
        "phase": node.get("phase"),
        "current_fact": node.get("fact"),
        "current_evidence_status": node.get("evidence_status"),
        "current_gap_reason": node.get("gap_reason"),
        "candidate_source_url": audit.get("source_url") or audit.get("canonical_url"),
        "candidate_source_tier": audit.get("source_tier"),
        "candidate_decision": audit.get("decision"),
        "candidate_fact_status": audit.get("fact_status"),
        "evidence_quote": evidence_quote,
        "evidence_locator": audit.get("evidence_locator"),
        "snapshot_path": snapshot_path,
        "snapshot_exists": snapshot_exists,
        "snapshot_sha256_declared": declared_sha,
        "snapshot_sha256_actual": actual_sha,
        "snapshot_hash_match": hash_match,
        "quote_present_in_snapshot": quote_present,
        "semantic_status": semantic_status,
        "occurred_at_candidate": occurred.get("value"),
        "occurred_at_verification_status": occurred.get("status", "UNVERIFIED"),
        "occurred_at_locator": occurred.get("locator"),
        "occurred_at_accepted": occurred_accepted,
        "first_public_at_candidate": first_public.get("value"),
        "first_public_at_verification_status": first_public.get("status", "UNVERIFIED"),
        "first_public_at_locator": first_public.get("locator"),
        "first_public_at_accepted": first_public_accepted,
        "blocking_reasons": blockers,
        "next_evidence_required": NEXT_EVIDENCE_REQUIRED.get(node_id),
        "promotion_eligible": promotion_eligible,
        "formal_ready": False,
    }


def write_gap_resolution_bundle(output_root: Path, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    ordered = sorted((dict(row) for row in rows), key=lambda row: row["fast_node_id"])
    _write_jsonl(output_root / "gap_resolution_candidates.jsonl", ordered)
    hard_failures = []
    ids = [row["gap_resolution_id"] for row in ordered]
    if len(ids) != len(set(ids)):
        hard_failures.append("DUPLICATE_GAP_RESOLUTION_ID")
    for row in ordered:
        if row.get("current_evidence_status") == "PENDING_EVIDENCE" and row.get("promotion_eligible"):
            hard_failures.append(f"PENDING_BUT_PROMOTABLE:{row['fast_node_id']}")
    validation = {
        "valid": not hard_failures,
        "hard_failures": hard_failures,
        "record_count": len(ordered),
        "promotion_eligible_count": sum(bool(row.get("promotion_eligible")) for row in ordered),
        "remaining_pending_count": sum(not bool(row.get("promotion_eligible")) for row in ordered),
        "snapshot_available_count": sum(bool(row.get("snapshot_exists")) for row in ordered),
        "snapshot_hash_match_count": sum(bool(row.get("snapshot_hash_match")) for row in ordered),
        "formal_ready": False,
    }
    summary = {
        "dataset_version": DATASET_VERSION,
        "release_tier": RELEASE_TIER,
        "record_count": validation["record_count"],
        "promotion_eligible_count": validation["promotion_eligible_count"],
        "remaining_pending_count": validation["remaining_pending_count"],
        "snapshot_available_count": validation["snapshot_available_count"],
        "snapshot_hash_match_count": validation["snapshot_hash_match_count"],
        "formal_ready": False,
        "source_timeline_modified": False,
    }
    _write_json(output_root / "validation_report.json", validation)
    _write_json(output_root / "summary.json", summary)
    (output_root / "README.md").write_text(
        "# Timeline Gap Resolution Candidate\n\n"
        "Read-only audit of the eight fixed pending timeline nodes. A located page or fact quote does not independently verify exact occurrence and first-public timestamps.\n",
        encoding="utf-8",
    )
    files = [output_root / "gap_resolution_candidates.jsonl", output_root / "validation_report.json", output_root / "summary.json", output_root / "README.md"]
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


def build_gap_resolution_bundle(root: Path, output_root: Path) -> dict[str, Any]:
    root = root.resolve()
    output_root = output_root.resolve()
    protected = [(root / name).resolve() for name in ("data", "code", "ui")]
    if any(output_root == path or path in output_root.parents for path in protected):
        raise ValueError("output_root must remain outside protected production and UI directories")
    timeline_root = root / "work/timeline_fast_candidate_v2"
    nodes = select_gap_nodes(_read_jsonl(timeline_root / "timeline_nodes.jsonl"))
    audits = {str(row.get("semantic_alignment_target")): row for row in _read_jsonl(timeline_root / "candidate_source_audit.jsonl")}
    manifests = {str(row.get("attachment_node_id")): row for row in _read_jsonl(timeline_root / "candidate_source_manifest.jsonl")}
    rows = []
    for node in nodes:
        node_id = str(node["fast_node_id"])
        rows.append(evaluate_gap_candidate(node, audits.get(node_id, {}), manifests.get(node_id, {}), timeline_root))
    manifest = write_gap_resolution_bundle(output_root, rows)
    return {
        "record_count": len(rows),
        "promotion_eligible_count": sum(row["promotion_eligible"] for row in rows),
        "remaining_pending_count": sum(not row["promotion_eligible"] for row in rows),
        "manifest_file_count": len(manifest["files"]),
        "formal_ready": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("work/timeline_gap_resolution_v1_candidate"))
    args = parser.parse_args(argv)
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    print(json.dumps(build_gap_resolution_bundle(root, output), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
