from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STABLE_UI = ROOT / "work" / "company_impact_high_quality_v2_candidate" / "ui"
VERSIONS = STABLE_UI / "versions"
LATEST = STABLE_UI / "latest_release.json"
PREFIX = "window.FINGOOSE_COMPANY_IMPACT_V2="
GATE = "strict-claim-closure-v2"
LEGACY_IDS = [f"event-{index:02d}" for index in range(1, 11)]
NEW_IDS = [f"event-{index:02d}" for index in range(11, 18)]


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def value_sha(value: Any) -> str:
    return sha256(canonical(value)).hexdigest()


def file_sha(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_bytes(canonical(value))


def load_bundle(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith(PREFIX):
        raise ValueError("UI_BUNDLE_PREFIX_INVALID")
    payload = text[len(PREFIX):].strip()
    if payload.endswith(";"):
        payload = payload[:-1]
    value = json.loads(payload)
    if not isinstance(value, dict) or not isinstance(value.get("events"), list):
        raise ValueError("UI_BUNDLE_SCHEMA_INVALID")
    return value


def write_bundle(path: Path, value: dict[str, Any]) -> None:
    path.write_text(PREFIX + json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + ";\n", encoding="utf-8", newline="\n")


def event_hashes(bundle: dict[str, Any]) -> dict[str, str]:
    return {str(event["event_id"]): value_sha(event) for event in bundle["events"]}


def freeze_baseline(version: str) -> Path:
    target = VERSIONS / version
    if target.exists():
        raise FileExistsError(f"IMMUTABLE_VERSION_EXISTS:{target}")
    target.mkdir(parents=True)
    for name in ("index.html", "ui_data_bundle.js"):
        shutil.copy2(STABLE_UI / name, target / name)
    bundle = load_bundle(target / "ui_data_bundle.js")
    ids = [str(row.get("event_id") or "") for row in bundle["events"]]
    if ids != LEGACY_IDS:
        raise ValueError("BASELINE_EVENT_ORDER_INVALID")
    manifest = {
        "version_id": version,
        "parent_version": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "immutable": True,
        "release_state": "STABLE_BASELINE",
        "gate_version": "PREVIOUS_GATE",
        "event_count": len(ids),
        "event_ids": ids,
        "event_status": {event_id: "FROZEN_UNDER_PREVIOUS_GATE" for event_id in ids},
        "event_sha256": event_hashes(bundle),
        "artifact_sha256": {
            "index.html": file_sha(target / "index.html"),
            "ui_data_bundle.js": file_sha(target / "ui_data_bundle.js"),
        },
        "legacy_encoding_note": "Frozen bytes may contain historical mojibake; baseline hashes take precedence in this release chain.",
        "review_status": "NEEDS_HUMAN_REVIEW",
        "formal_ready": False,
    }
    write_json(target / "release_manifest.json", manifest)
    return target


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON_OBJECT_REQUIRED:{path}")
    return value


def build_candidate(
    version: str,
    parent_version: str,
    run_dir: Path,
    adapter_bundle: Path,
    research_run_id: str | None = None,
) -> Path:
    parent = VERSIONS / parent_version
    target = VERSIONS / version
    if target.exists():
        raise FileExistsError(f"IMMUTABLE_VERSION_EXISTS:{target}")
    gate = load_json(run_dir / "batch_gate_report.json")
    if gate.get("release_eligible") is not True or gate.get("accepted_event_ids") != NEW_IDS:
        raise ValueError("ATOMIC_BATCH_NOT_RELEASE_ELIGIBLE")
    parent_manifest = load_json(parent / "release_manifest.json")
    candidate = load_bundle(adapter_bundle)
    ids = [str(row.get("event_id") or "") for row in candidate["events"]]
    if ids != LEGACY_IDS + NEW_IDS:
        raise ValueError("CANDIDATE_EVENT_ORDER_INVALID")
    hashes = event_hashes(candidate)
    for event_id in LEGACY_IDS:
        if hashes[event_id] != parent_manifest["event_sha256"][event_id]:
            raise ValueError(f"LEGACY_EVENT_HASH_DRIFT:{event_id}")
    target.mkdir(parents=True)
    shutil.copy2(parent / "index.html", target / "index.html")
    shutil.copy2(adapter_bundle, target / "ui_data_bundle.js")
    artifacts = {
        "index.html": file_sha(target / "index.html"),
        "ui_data_bundle.js": file_sha(target / "ui_data_bundle.js"),
        "batch_gate_report.json": file_sha(run_dir / "batch_gate_report.json"),
        "validation_report.json": file_sha(run_dir / "validation_report.json"),
        "reproducibility_report.json": file_sha(run_dir / "reproducibility_report.json"),
    }
    screenshot_report = run_dir / "ui_acceptance_report.json"
    if screenshot_report.is_file():
        artifacts["ui_acceptance_report.json"] = file_sha(screenshot_report)
    manifest = {
        "version_id": version,
        "parent_version": parent_version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "immutable": True,
        "release_state": "CANDIDATE_AWAITING_HUMAN_PROMOTION",
        "gate_version": GATE,
        "research_run_id": research_run_id or run_dir.name,
        "ui_preparation_run_id": run_dir.name,
        "event_count": len(ids),
        "event_ids": ids,
        "event_status": {
            **{event_id: "FROZEN_UNDER_PREVIOUS_GATE" for event_id in LEGACY_IDS},
            **{event_id: "MACHINE_VALIDATED_NEEDS_HUMAN_REVIEW" for event_id in NEW_IDS},
        },
        "event_sha256": hashes,
        "artifact_sha256": artifacts,
        "review_status": "NEEDS_HUMAN_REVIEW",
        "formal_ready": False,
        "causal_conclusion": "ABSTAIN",
    }
    write_json(target / "release_manifest.json", manifest)
    return target


def verify(version: str) -> dict[str, Any]:
    target = VERSIONS / version
    manifest = load_json(target / "release_manifest.json")
    bundle = load_bundle(target / "ui_data_bundle.js")
    errors: list[str] = []
    ids = [str(row.get("event_id") or "") for row in bundle["events"]]
    if ids != manifest.get("event_ids"):
        errors.append("MANIFEST_EVENT_ORDER_MISMATCH")
    if event_hashes(bundle) != manifest.get("event_sha256"):
        errors.append("EVENT_HASH_MISMATCH")
    for name in ("index.html", "ui_data_bundle.js"):
        expected = manifest.get("artifact_sha256", {}).get(name)
        if expected != file_sha(target / name):
            errors.append(f"ARTIFACT_HASH_MISMATCH:{name}")
    return {"version_id": version, "valid": not errors, "errors": errors, "event_count": len(ids)}


def promote(version: str, confirmed_by: str) -> None:
    result = verify(version)
    if not result["valid"]:
        raise ValueError("VERSION_VERIFY_FAILED:" + ",".join(result["errors"]))
    target = VERSIONS / version
    manifest = load_json(target / "release_manifest.json")
    if manifest.get("release_state") != "CANDIDATE_AWAITING_HUMAN_PROMOTION":
        raise ValueError("VERSION_NOT_PROMOTABLE")
    bundle_tmp = STABLE_UI / ".ui_data_bundle.js.promote.tmp"
    latest_tmp = STABLE_UI / ".latest_release.json.promote.tmp"
    shutil.copy2(target / "ui_data_bundle.js", bundle_tmp)
    write_json(latest_tmp, {
        "version_id": version,
        "promoted_at": datetime.now(timezone.utc).isoformat(),
        "confirmed_by": confirmed_by,
        "bundle_sha256": file_sha(bundle_tmp),
        "event_count": manifest["event_count"],
        "review_status": "NEEDS_HUMAN_REVIEW",
        "formal_ready": False,
    })
    os.replace(bundle_tmp, STABLE_UI / "ui_data_bundle.js")
    os.replace(latest_tmp, LATEST)


def main() -> int:
    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(dest="command", required=True)
    stage = subs.add_parser("freeze-baseline")
    stage.add_argument("--version", required=True)
    stage = subs.add_parser("build-candidate")
    stage.add_argument("--version", required=True)
    stage.add_argument("--parent-version", required=True)
    stage.add_argument("--run-dir", type=Path, required=True)
    stage.add_argument("--adapter-bundle", type=Path, required=True)
    stage.add_argument("--research-run-id")
    stage = subs.add_parser("verify")
    stage.add_argument("--version", required=True)
    stage = subs.add_parser("promote")
    stage.add_argument("--version", required=True)
    stage.add_argument("--confirmed-by", required=True)
    args = parser.parse_args()
    if args.command == "freeze-baseline":
        print(freeze_baseline(args.version))
    elif args.command == "build-candidate":
        print(build_candidate(
            args.version,
            args.parent_version,
            args.run_dir.resolve(),
            args.adapter_bundle.resolve(),
            args.research_run_id,
        ))
    elif args.command == "verify":
        result = verify(args.version)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result["valid"] else 1
    else:
        promote(args.version, args.confirmed_by)
        print(args.version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
