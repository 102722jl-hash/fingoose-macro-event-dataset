from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "work" / "skill_research_runs" / "run-fingoose-strict-claim-closure-v2-20260813-005"
UI = ROOT / "work" / "company_impact_high_quality_v2_candidate" / "ui"
R000 = UI / "versions" / "fingoose-ui-20260813-r000"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def digest(path: Path) -> str:
    value = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> None:
    statuses = read_jsonl(RUN / "event_processing_status.jsonl")
    validation = read_json(RUN / "validation_report.json")
    replay = read_json(RUN / "reproducibility_report.json")
    gate = read_json(RUN / "batch_gate_report.json")
    r000 = read_json(R000 / "release_manifest.json")
    stable_bundle_hash = digest(UI / "ui_data_bundle.js")
    baseline_bundle_hash = digest(R000 / "ui_data_bundle.js")
    report = {
        "run_id": RUN.name,
        "policy": "strict-claim-closure-v2",
        "candidate_created": True,
        "machine_validated_frozen_baseline": validation.get("valid") is True and not validation.get("errors") and not validation.get("warnings"),
        "machine_validated_new_events": [],
        "human_review_required": True,
        "formal_ready": False,
        "causal_conclusion": "ABSTAIN",
        "events": statuses,
        "batch_gate": gate,
        "quarantined_event_ids": [row["event_id"] for row in statuses if row["processing_status"] == "QUARANTINED_STRICT"],
        "build": {
            "return_codes": read_json(RUN / "build_results.json")["return_codes"],
            "candidate_event_count": validation["counts"]["unified_events"],
            "note": "Only the frozen 10-event baseline was built because accepted_content is empty.",
        },
        "validation": {
            "valid": validation["valid"],
            "error_count": len(validation["errors"]),
            "warning_count": len(validation["warnings"]),
        },
        "offline_replay": replay,
        "ui_release": {
            "baseline_version": r000["version_id"],
            "baseline_valid": stable_bundle_hash == baseline_bundle_hash,
            "stable_bundle_sha256": stable_bundle_hash,
            "baseline_bundle_sha256": baseline_bundle_hash,
            "candidate_version_created": False,
            "candidate_version_reason": "ATOMIC_BATCH_EVENT_SET_INCOMPLETE",
            "screenshot_acceptance": "NOT_RUN_BATCH_GATE_FAILED",
            "promotion_performed": False,
        },
        "artifact_sha256": {
            name: digest(RUN / name) for name in (
                "candidate_master_data.jsonl",
                "candidate_sft_dataset.jsonl",
                "split_manifest.json",
                "validation_report.json",
                "content_candidates.jsonl",
                "accepted_content.jsonl",
                "quarantine.jsonl",
                "gap_manifest.jsonl",
            )
        },
    }
    (RUN / "implementation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({
        "accepted": len(gate["accepted_event_ids"]),
        "quarantined": len(report["quarantined_event_ids"]),
        "validation_errors": report["validation"]["error_count"],
        "validation_warnings": report["validation"]["warning_count"],
        "replay_stable": replay["stable"],
        "r001_created": report["ui_release"]["candidate_version_created"],
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
