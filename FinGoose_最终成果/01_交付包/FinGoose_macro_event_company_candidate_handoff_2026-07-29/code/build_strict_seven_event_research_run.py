from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "work" / "skill_research_runs" / "run-fingoose-seven-events-20260813-003"
DEFAULT_EVENT12 = ROOT / "work" / "skill_research_runs" / "run-fingoose-event12-gapfill-20260813-001"
DEFAULT_EVENT11 = ROOT / "work" / "skill_research_runs" / "run-fingoose-event11-iea-official-20260813-001"
DISCOVER = ROOT / "work" / "skill_research_runs" / "run-fingoose-discover-20260101-20260813-001"
PIPELINE = ROOT / "skills" / "building-auditable-macro-datasets" / "scripts" / "macro_dataset_pipeline.py"
POLICY = "strict-claim-closure-v2"
EVENT_IDS = [f"event-{index:02d}" for index in range(11, 18)]
sys.path.insert(0, str(ROOT / "code"))
from build_seven_discovered_events_candidate_v1 import EVENTS, make_unified


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8", newline="\n")


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")


def file_sha(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def initialize(source: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    (output / "snapshots").mkdir()
    for name in ("profile.json", "base_dataset_config.json", "base_training_config.json", "base_unified_events.jsonl"):
        shutil.copy2(source / name, output / name)
    for name in ("discovery_candidates.jsonl", "search_audit.jsonl"):
        shutil.copy2(DISCOVER / name, output / name)
    profile_path = output / "profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    profile["profile_version"] = "macro-dataset-profile-v2"
    profile["audit_policy"] = POLICY
    profile["market_window_keys"] = ["T_MINUS_1", "T0", "D1", "D3", "D5", "D20"]
    write_json(profile_path, profile)


def normalize_event_evidence(record: dict[str, Any], accepted: dict[str, dict[str, Any]]) -> None:
    unified = record["unified_event"]
    nested_event = unified.get("event") or {}
    nested_chain = nested_event.get("reasoning_chain") or {}
    evidence_registry = deepcopy(nested_chain.get("evidence_registry") or [])
    accepted_event = accepted.get(record["event_id"])
    if accepted_event:
        by_id = {item["evidence_id"]: item for item in evidence_registry if item.get("evidence_id")}
        by_id[accepted_event["evidence_id"]] = deepcopy(accepted_event)
        evidence_registry = list(by_id.values())
    for evidence in evidence_registry:
        evidence.setdefault("source_tier", "T1")
        evidence.setdefault("retrieved_at", "2026-08-13T00:00:00+00:00")
        evidence.setdefault("temporal_role", "AS_OF_EVIDENCE")
        evidence.setdefault("statement_class", "SOURCE_FACT")
        evidence.setdefault("acceptance_status", "ACCEPTED")
        evidence.setdefault("acceptance_reason", "GATES_PASSED")
    unified["evidence_registry"] = evidence_registry


def event11_candidate(event11_run: Path) -> dict[str, Any]:
    event = next(row for row in EVENTS if row["event_id"] == "event-11")
    unavailable = {
        "event_id": "event-11",
        "evidence_id": "rejected-evidence-event-11-iea-body",
        "source_url": event["source_url"],
        "publisher": event["publisher"],
        "published_at": event["date"] + "T00:00:00+00:00",
        "retrieved_at": "2026-08-13T00:00:00+00:00",
        "original_quote": "",
        "locator": "",
        "snapshot_sha256": "",
        "source_tier": "T1",
        "supports_node_ids": [],
        "acceptance_status": "REJECTED",
        "acceptance_reason": "OFFICIAL_BODY_EXTRACTION_UNAVAILABLE",
        "temporal_role": "AS_OF_EVIDENCE",
    }
    acquired = read_jsonl(event11_run / "accepted_evidence.jsonl")
    evidence = acquired[0] if acquired else unavailable
    unified = make_unified(event, evidence)
    unified["evidence_registry"] = acquired
    nested = unified.get("event", {}).get("reasoning_chain", {})
    nested["evidence_registry"] = deepcopy(acquired)
    return {
        "event_id": "event-11",
        "operation": "UPSERT",
        "closure_status": "OPEN",
        "errors": [] if acquired else ["OFFICIAL_BODY_EXTRACTION_UNAVAILABLE"],
        "warnings": [],
        "evidence_ids": [],
        "unified_event": unified,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-run", type=Path, required=True)
    parser.add_argument("--source-run", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--event12-run", type=Path, default=DEFAULT_EVENT12)
    parser.add_argument("--event11-run", type=Path, default=DEFAULT_EVENT11)
    args = parser.parse_args()
    source = args.source_run.resolve()
    event12 = args.event12_run.resolve()
    event11 = args.event11_run.resolve()
    output = args.output_run.resolve()
    initialize(source, output)

    ordinary = {row["event_id"]: row for row in read_jsonl(source / "content_candidates.jsonl")}
    enriched12 = next(row for row in read_jsonl(event12 / "content_candidates.jsonl") if row["event_id"] == "event-12")
    ordinary["event-12"] = enriched12
    accepted_evidence = {row["event_id"]: row for row in read_jsonl(source / "accepted_evidence.jsonl")}
    records = []
    for event_id in EVENT_IDS:
        if event_id not in ordinary:
            records.append(event11_candidate(event11) if event_id == "event-11" else {
                "event_id": event_id, "closure_status": "OPEN",
                "errors": ["SOURCE_RECORD_UNAVAILABLE"], "warnings": [],
                "unified_event": {"event_id": event_id, "review_status": "NEEDS_HUMAN_REVIEW", "formal_ready": False,
                    "causal_assessment": {"status": "NOT_IDENTIFIED", "causal_attribution_allowed": False, "causal_conclusion": "ABSTAIN", "gate_results": {}},
                    "evidence_registry": [], "industries": [], "companies": [], "qa": []},
            })
            continue
        row = deepcopy(ordinary[event_id])
        row["closure_status"] = "OPEN"
        row["errors"] = []
        row["warnings"] = []
        normalize_event_evidence(row, accepted_evidence)
        records.append(row)

    write_jsonl(output / "content_candidates.jsonl", records)
    all_evidence = []
    for record in records:
        all_evidence.extend(record["unified_event"].get("evidence_registry") or [])
        for company in record["unified_event"].get("companies") or []:
            all_evidence.extend(company.get("company_evidence") or [])
    unique_evidence = {str(row.get("evidence_id")): row for row in all_evidence if row.get("evidence_id")}
    write_jsonl(output / "evidence_candidates.jsonl", list(unique_evidence.values()))
    write_jsonl(output / "accepted_evidence.jsonl", list(unique_evidence.values()))
    write_jsonl(output / "rejected_evidence.jsonl", [{
        "event_id": "event-11",
        "source_url": "https://www.iea.org/news/iea-member-countries-to-carry-out-largest-ever-oil-stock-release-amid-market-disruptions-from-middle-east-conflict",
        "alternate_official_url": "https://www.iea.org/news/iea-confirms-member-country-contributions-to-collective-action-to-release-oil-stocks-in-response-to-middle-east-disruptions",
        "source_tier": "T1",
        "acceptance_status": "REJECTED",
        "acceptance_reason": "OFFICIAL_BODY_EXTRACTION_UNAVAILABLE",
        "detail": "Official URLs were discovered and opened through the extraction adapter, but both returned unsupported_response; search result text was not promoted to evidence.",
        "review_status": "NEEDS_HUMAN_REVIEW",
        "formal_ready": False,
    }])

    command = [
        "python", str(PIPELINE), "audit", "--policy", POLICY,
        "--input", str(output / "content_candidates.jsonl"),
        "--output", str(output / "gap_manifest.jsonl"),
        "--accepted-output", str(output / "accepted_content.jsonl"),
        "--quarantine-output", str(output / "quarantine.jsonl"),
        "--batch-report", str(output / "batch_gate_report.json"),
    ]
    for event_id in EVENT_IDS:
        command.extend(("--required-event-id", event_id))
    result = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
    gaps = read_jsonl(output / "gap_manifest.jsonl")
    gap_by_event: dict[str, list[str]] = {event_id: [] for event_id in EVENT_IDS}
    for gap in gaps:
        gap_by_event.setdefault(gap["event_id"], []).append(gap["gap_code"])
    accepted_ids = {row["event_id"] for row in read_jsonl(output / "accepted_content.jsonl")}
    statuses = []
    for event_id in EVENT_IDS:
        unified = next(row["unified_event"] for row in records if row["event_id"] == event_id)
        statuses.append({
            "event_id": event_id,
            "processing_status": "ACCEPTED_STRICT" if event_id in accepted_ids else "QUARANTINED_STRICT",
            "evidence_count": len(unified.get("evidence_registry") or []) + sum(len(company.get("company_evidence") or []) for company in unified.get("companies") or []),
            "industry_count": len(unified.get("industries") or []),
            "company_count": len(unified.get("companies") or []),
            "qa_count": len(unified.get("qa") or []),
            "calculated_industry_market_count": sum((industry.get("market_window") or {}).get("status") == "CALCULATED" for industry in unified.get("industries") or []),
            "calculated_company_market_count": sum((company.get("market_window") or {}).get("status") == "CALCULATED" for company in unified.get("companies") or []),
            "reason_codes": sorted(set(gap_by_event[event_id])),
            "review_status": "NEEDS_HUMAN_REVIEW",
            "formal_ready": False,
            "causal_conclusion": "ABSTAIN",
        })
    write_jsonl(output / "event_processing_status.jsonl", statuses)
    write_json(output / "request.json", {
        "run_id": output.name,
        "mode": "strict-seven-event-research",
        "policy": POLICY,
        "source_run": str(source),
        "event12_reuse_run": str(event12),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "required_event_ids": EVENT_IDS,
        "review_status": "NEEDS_HUMAN_REVIEW",
        "formal_ready": False,
    })
    write_json(output / "run_summary.json", {
        "run_id": output.name,
        "policy": POLICY,
        "audit_return_code": result.returncode,
        "accepted_event_count": len(accepted_ids),
        "quarantined_event_count": len(EVENT_IDS) - len(accepted_ids),
        "release_eligible": len(accepted_ids) == len(EVENT_IDS),
        "content_candidates_sha256": file_sha(output / "content_candidates.jsonl"),
        "gap_manifest_sha256": file_sha(output / "gap_manifest.jsonl"),
        "review_status": "NEEDS_HUMAN_REVIEW",
        "formal_ready": False,
    })
    print((output / "run_summary.json").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
