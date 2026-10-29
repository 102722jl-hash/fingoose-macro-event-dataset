from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "skills" / "building-auditable-macro-datasets" / "scripts" / "macro_dataset_pipeline.py"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def canonical_sha(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    return sha256(payload.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-run", type=Path, required=True)
    parser.add_argument("--output-run", type=Path, required=True)
    args = parser.parse_args()
    source, output = args.input_run.resolve(), args.output_run.resolve()
    shutil.copytree(source, output)

    record = read_jsonl(output / "accepted_content.jsonl")[0]
    event_id = str(record["event_id"])
    unified = deepcopy(record["unified_event"])
    research = unified.get("research_content") or {}
    research["industry_impacts"] = deepcopy(unified["industries"])
    research["company_impacts"] = deepcopy(unified["companies"])
    research["qa_sections"] = deepcopy(unified["qa"])
    research["evidence_registry"] = deepcopy(unified["evidence_registry"])
    unified["research_content"] = research

    updated = {**record, "unified_event": unified, "content_sha256": canonical_sha(unified)}
    write_jsonl(output / "content_candidates.jsonl", [updated])
    command = [
        "python", str(PIPELINE), "audit", "--policy", "strict-claim-closure-v2",
        "--input", str(output / "content_candidates.jsonl"),
        "--output", str(output / "gap_manifest.jsonl"),
        "--accepted-output", str(output / "accepted_content.jsonl"),
        "--quarantine-output", str(output / "quarantine.jsonl"),
        "--batch-report", str(output / "batch_gate_report.json"),
        "--required-event-id", event_id,
    ]
    result = subprocess.run(command, cwd=ROOT, check=False)
    accepted = read_jsonl(output / "accepted_content.jsonl")
    gaps = read_jsonl(output / "gap_manifest.jsonl")
    summary = {
        "run_id": output.name,
        "event_id": event_id,
        "status": "ACCEPTED_STRICT" if result.returncode == 0 and len(accepted) == 1 else "QUARANTINED",
        "audit_return_code": result.returncode,
        "gap_codes": sorted({row.get("gap_code") for row in gaps if row.get("gap_code")}),
        "company_codes_aligned": [row["company_code"] for row in unified["companies"]]
        == [row["company_code"] for row in research["company_impacts"]],
        "review_status": "NEEDS_HUMAN_REVIEW",
        "formal_ready": False,
        "causal_conclusion": "ABSTAIN",
    }
    (output / "run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
