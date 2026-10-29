from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from build_candidate_run_ui_preview import build_event, read_jsonl
from fingoose_ui_release import load_bundle, write_bundle


NEW_IDS = [f"event-{index:02d}" for index in range(11, 18)]


def event_evidence(unified: dict[str, Any]) -> dict[str, Any]:
    registry = unified.get("evidence_registry") or []
    if not registry:
        raise ValueError(f"EVENT_EVIDENCE_MISSING:{unified.get('event_id')}")
    return registry[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-bundle", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-bundle", type=Path, required=True)
    args = parser.parse_args()

    baseline = load_bundle(args.baseline_bundle.resolve())
    records = read_jsonl(args.run_dir.resolve() / "accepted_content.jsonl")
    by_id = {str(row["event_id"]): row["unified_event"] for row in records}
    if sorted(by_id) != NEW_IDS:
        raise ValueError("ATOMIC_ACCEPTED_EVENT_SET_INVALID")

    candidate = deepcopy(baseline)
    new_events = [build_event(by_id[event_id], event_evidence(by_id[event_id])) for event_id in NEW_IDS]
    candidate["events"] = [*baseline["events"], *new_events]
    candidate["dataset_version"] = f"{baseline['dataset_version']}:strict-claim-closure-v2:{args.run_dir.resolve().name}"
    candidate["formal_ready"] = False
    candidate["sha_gate"] = "MACHINE_VALIDATED_NEEDS_HUMAN_REVIEW"

    summary = deepcopy(baseline.get("summary") or {})
    summary["event_count"] = len(candidate["events"])
    summary["company_evaluation_count"] = sum(len(event.get("companies") or []) for event in candidate["events"])
    summary["industry_mapping_count"] = sum(len(event.get("industry_impacts") or []) for event in candidate["events"])
    summary["qa_case_count"] = sum(len(event.get("qa") or []) for event in candidate["events"])
    summary["timeline_node_count"] = sum(len(event.get("timeline") or []) for event in candidate["events"])
    summary["transmission_path_count"] = int(summary.get("transmission_path_count") or 0) + sum(
        len(event.get("operating_transmission_paths") or []) for event in new_events
    )
    summary["gate_version"] = "strict-claim-closure-v2"
    summary["research_run_id"] = args.run_dir.resolve().name
    summary["review_status"] = "NEEDS_HUMAN_REVIEW"
    candidate["summary"] = summary

    args.output_bundle.resolve().parent.mkdir(parents=True, exist_ok=True)
    write_bundle(args.output_bundle.resolve(), candidate)
    print(json.dumps({
        "event_count": summary["event_count"],
        "company_count": summary["company_evaluation_count"],
        "industry_count": summary["industry_mapping_count"],
        "qa_count": summary["qa_case_count"],
        "event_ids": [event["event_id"] for event in candidate["events"]],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
