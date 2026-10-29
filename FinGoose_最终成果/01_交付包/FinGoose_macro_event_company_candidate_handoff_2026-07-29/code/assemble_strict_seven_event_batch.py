from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "skills" / "building-auditable-macro-datasets" / "scripts" / "macro_dataset_pipeline.py"
EVENT_IDS = [f"event-{index:02d}" for index in range(11, 18)]
DEFAULT_RUNS = {
    "event-11": "run-fingoose-event11-strict-closure-20260814-002",
    "event-12": "run-fingoose-event12-strict-closure-20260814-003",
    "event-13": "run-fingoose-event13-strict-closure-20260814-004",
    "event-14": "run-fingoose-event14-strict-closure-20260814-001",
    "event-15": "run-fingoose-event15-strict-closure-20260814-001",
    "event-16": "run-fingoose-event16-strict-closure-20260814-003",
    "event-17": "run-fingoose-event17-strict-closure-20260814-001",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8", newline="\n")


def merge_snapshots(source: Path, target: Path) -> None:
    if not source.is_dir():
        raise FileNotFoundError(f"SNAPSHOT_DIRECTORY_MISSING:{source}")
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        destination = target / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if destination.read_bytes() != path.read_bytes():
                raise ValueError(f"SNAPSHOT_PATH_CONFLICT:{destination}")
            continue
        shutil.copy2(path, destination)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-run", type=Path, required=True)
    parser.add_argument("--baseline-run", type=Path, required=True)
    args = parser.parse_args()
    output, baseline = args.output_run.resolve(), args.baseline_run.resolve()
    output.mkdir(parents=True, exist_ok=False)
    for name in ("profile.json", "base_dataset_config.json", "base_training_config.json", "base_unified_events.jsonl"):
        shutil.copy2(baseline / name, output / name)
    records, evidence = [], {}
    snapshots = output / "snapshots"
    snapshots.mkdir()
    runs_root = ROOT / "work" / "skill_research_runs"
    for event_id, run_name in DEFAULT_RUNS.items():
        run = runs_root / run_name
        record = read_jsonl(run / "accepted_content.jsonl")[0]
        records.append(record)
        for row in read_jsonl(run / "accepted_evidence.jsonl"):
            evidence[row["evidence_id"]] = row
        merge_snapshots(run / "snapshots", snapshots)
    records.sort(key=lambda row: row["event_id"])
    write_jsonl(output / "content_candidates.jsonl", records)
    write_jsonl(output / "accepted_evidence.jsonl", list(evidence.values()))
    command = ["python", str(PIPELINE), "audit", "--policy", "strict-claim-closure-v2", "--input", str(output / "content_candidates.jsonl"), "--output", str(output / "gap_manifest.jsonl"), "--accepted-output", str(output / "accepted_content.jsonl"), "--quarantine-output", str(output / "quarantine.jsonl"), "--batch-report", str(output / "batch_gate_report.json")]
    for event_id in EVENT_IDS: command.extend(("--required-event-id", event_id))
    result = subprocess.run(command, cwd=ROOT, check=False)
    accepted = read_jsonl(output / "accepted_content.jsonl")
    gaps = read_jsonl(output / "gap_manifest.jsonl")
    summary = {"run_id": output.name, "policy": "strict-claim-closure-v2", "required_event_ids": EVENT_IDS, "accepted_event_ids": [row["event_id"] for row in accepted], "quarantined_event_ids": sorted({row["event_id"] for row in gaps}), "release_eligible": len(accepted) == 7, "audit_return_code": result.returncode, "content_candidates_sha256": sha256((output / "content_candidates.jsonl").read_bytes()).hexdigest(), "review_status": "NEEDS_HUMAN_REVIEW", "formal_ready": False, "causal_conclusion": "ABSTAIN"}
    (output / "run_summary.json").write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
