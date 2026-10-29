from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Mapping, Sequence

from audit_outputs import (
    STRICT_POLICY,
    assemble_candidate_master,
    build_event_splits,
    partition_candidates,
    strict_claim_closure_gaps,
    validate_atomic_batch,
    write_json,
)
from audit_outputs import compare_artifact_sets, validate_replay_inputs


class OfflineNetworkAccessError(RuntimeError):
    pass


class OfflineGenerationAccessError(RuntimeError):
    pass


def _stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{prefix}-{sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def deduplicate_candidates(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        urls = sorted(str(value) for value in row.get("official_seed_urls") or [] if value)
        fingerprint = {
            "anchor_at": str(row.get("anchor_at") or ""),
            "official_seed_urls": urls,
        }
        key = _stable_id("candidate-event", fingerprint)
        unique.setdefault(
            key,
            {
                **dict(row),
                "candidate_event_id": key,
                "deduplication_fingerprint": key,
            },
        )
    return [unique[key] for key in sorted(unique)]


def scan_record_gaps(
    record: Mapping[str, Any], *, policy: str | None = None
) -> list[dict[str, str]]:
    event_id = str(record.get("event_id") or "")
    subject = record.get("unified_event") if isinstance(record.get("unified_event"), Mapping) else record
    codes: set[str] = set()
    for evidence in subject.get("evidence_registry") or []:
        if not evidence.get("original_quote"):
            codes.add("EVIDENCE_QUOTE_MISSING")
        if not evidence.get("locator"):
            codes.add("EVIDENCE_LOCATOR_MISSING")
        if not evidence.get("source_url"):
            codes.add("EVIDENCE_URL_MISSING")
    if not subject.get("industries"):
        codes.add("SUPPORTED_INDUSTRIES_MISSING")
    if not subject.get("companies"):
        codes.add("SUPPORTED_COMPANIES_MISSING")
    if not subject.get("qa"):
        codes.add("EVENT_QA_MISSING")
    if policy == STRICT_POLICY:
        codes.update(strict_claim_closure_gaps(record))
    return [{"event_id": event_id, "gap_code": code} for code in sorted(codes)]


def write_run_configs(
    run_dir: Path,
    base_dataset_config: Mapping[str, Any],
    base_training_config: Mapping[str, Any],
    splits: Mapping[str, list[str]],
) -> tuple[Path, Path]:
    dataset = dict(base_dataset_config)
    dataset["project_root"] = str(run_dir.resolve())
    dataset["sources"] = {
        "frozen": {
            "base_dir": ".",
            "files": {
                "profile": "profile.json",
                "base_dataset_config": "base_dataset_config.json",
                "base_training_config": "base_training_config.json",
                "base_unified_events": "base_unified_events.jsonl",
                "accepted_evidence": "accepted_evidence.jsonl",
                "accepted_content": "accepted_content.jsonl",
            },
        },
    }
    dataset.pop("content_alignment", None)
    dataset["outputs"] = {
        "unified_events": "candidate_master_data.jsonl",
        "sft_dataset": "candidate_sft_dataset.jsonl",
        "split_manifest": "split_manifest.json",
        "manifest": "manifest.json",
        "validation_report": "validation_report.json",
    }
    dataset["splits"] = dict(splits)
    run_config = run_dir / "dataset.run.json"
    write_json(run_config, dataset)

    training = dict(base_training_config)
    training["dataset_config"] = "dataset.run.json"
    training["sft_dataset"] = "candidate_sft_dataset.jsonl"
    training["dataset_manifest"] = "manifest.json"
    training["validation_report"] = "validation_report.json"
    training["runs_dir"] = "training-dry-runs"
    run_training_config = run_dir / "sft.run.json"
    write_json(run_training_config, training)
    return run_config, run_training_config


def materialize_command(
    command: Sequence[str], run_config: Path, run_training_config: Path
) -> list[str]:
    replacements = {
        "{run_config}": str(run_config),
        "{run_training_config}": str(run_training_config),
    }
    return [replacements.get(argument, argument) for argument in command]


def run_profile_commands(
    commands: Sequence[Sequence[str]],
    *,
    project_root: Path,
    run_config: Path,
    run_training_config: Path,
) -> list[subprocess.CompletedProcess[str]]:
    results = []
    environment = os.environ.copy()
    python_paths = [str(project_root / "training"), str(project_root)]
    if environment.get("PYTHONPATH"):
        python_paths.append(environment["PYTHONPATH"])
    environment["PYTHONPATH"] = os.pathsep.join(python_paths)
    for command in commands:
        materialized = materialize_command(command, run_config, run_training_config)
        results.append(
            subprocess.run(
                materialized,
                cwd=project_root,
                check=False,
                shell=False,
                text=True,
                capture_output=True,
                env=environment,
            )
        )
    return results


def validation_outcome(
    return_codes: Sequence[int], report: Mapping[str, Any]
) -> dict[str, Any]:
    eligible = (
        all(code == 0 for code in return_codes)
        and report.get("valid") is True
        and not report.get("errors")
        and not report.get("warnings")
    )
    return {
        "status": "CANDIDATE_SFT_ELIGIBLE" if eligible else "VALIDATION_FAILED",
        "NEEDS_HUMAN_REVIEW": True,
        "formal_ready": False,
        "command_return_codes": list(return_codes),
    }


def normalize_validation_report_paths(
    report: Mapping[str, Any],
) -> dict[str, Any]:
    normalized = json.loads(json.dumps(report, ensure_ascii=False))
    for artifact in normalized.get("validated_artifacts", {}).values():
        if artifact.get("path"):
            artifact["path"] = Path(str(artifact["path"])).name
    return normalized


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def prepare_candidate_run(
    run_dir: Path, profile: Mapping[str, Any]
) -> dict[str, Path]:
    base_events = _read_jsonl(run_dir / "base_unified_events.jsonl")
    accepted_content = _read_jsonl(run_dir / "accepted_content.jsonl")
    base_dataset_config = _read_json(run_dir / "base_dataset_config.json")
    base_training_config = _read_json(run_dir / "base_training_config.json")
    candidate_master = assemble_candidate_master(base_events, accepted_content)
    master_path = run_dir / "candidate_master_data.jsonl"
    _write_jsonl(master_path, candidate_master)
    splits = build_event_splits(
        [str(row["event_id"]) for row in candidate_master],
        base_dataset_config.get("splits") or {},
        accepted_content,
        profile["split_policy"],
    )
    run_config, run_training_config = write_run_configs(
        run_dir, base_dataset_config, base_training_config, splits
    )
    return {
        "candidate_master_data": master_path,
        "run_config": run_config,
        "run_training_config": run_training_config,
    }


def _resolve_profile(profile_path: Path) -> tuple[dict[str, Any], Path]:
    profile_path = profile_path.resolve()
    profile = _read_json(profile_path)
    project_root = (profile_path.parent / str(profile["project_root"])).resolve()
    return profile, project_root


def _run_dir(profile: Mapping[str, Any], project_root: Path, run_id: str) -> Path:
    return (project_root / str(profile["research_runs_dir"]) / run_id).resolve()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        records.append(value)
    return records


def _write_jsonl(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for record in records
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def _run_discover(args: argparse.Namespace) -> int:
    _write_jsonl(args.output, deduplicate_candidates(_read_jsonl(args.input)))
    return 0


def _run_audit(args: argparse.Namespace) -> int:
    records = _read_jsonl(args.input)
    gaps = [gap for record in records for gap in scan_record_gaps(record, policy=args.policy)]
    _write_jsonl(args.output, gaps)
    if args.accepted_output or args.quarantine_output:
        accepted, quarantined = partition_candidates(records, policy=args.policy)
        if args.accepted_output:
            _write_jsonl(args.accepted_output, accepted)
        if args.quarantine_output:
            _write_jsonl(args.quarantine_output, quarantined)
        if args.required_event_id:
            batch_errors = validate_atomic_batch(accepted, args.required_event_id)
            if batch_errors:
                if args.batch_report:
                    write_json(args.batch_report, {
                        "policy": args.policy,
                        "required_event_ids": sorted(args.required_event_id),
                        "accepted_event_ids": sorted(str(row.get("event_id") or "") for row in accepted),
                        "release_eligible": False,
                        "reason_codes": batch_errors,
                    })
                return 2
            if args.batch_report:
                write_json(args.batch_report, {
                    "policy": args.policy,
                    "required_event_ids": sorted(args.required_event_id),
                    "accepted_event_ids": sorted(str(row.get("event_id") or "") for row in accepted),
                    "release_eligible": True,
                    "reason_codes": [],
                })
    return 0


def _run_build(args: argparse.Namespace) -> int:
    profile, project_root = _resolve_profile(args.profile)
    run_dir = _run_dir(profile, project_root, args.run_id)
    paths = prepare_candidate_run(run_dir, profile)
    results = run_profile_commands(
        profile["candidate_build_commands"],
        project_root=project_root,
        run_config=paths["run_config"],
        run_training_config=paths["run_training_config"],
    )
    write_json(
        run_dir / "build_results.json",
        {
            "return_codes": [result.returncode for result in results],
            "commands": [result.args for result in results],
        },
    )
    return 0 if all(result.returncode == 0 for result in results) else 1


def _run_validate(args: argparse.Namespace) -> int:
    profile, project_root = _resolve_profile(args.profile)
    run_dir = _run_dir(profile, project_root, args.run_id)
    run_config = run_dir / "dataset.run.json"
    run_training_config = run_dir / "sft.run.json"
    results = run_profile_commands(
        profile["validation_commands"],
        project_root=project_root,
        run_config=run_config,
        run_training_config=run_training_config,
    )
    report_path = run_dir / "validation_report.json"
    report = _read_json(report_path) if report_path.is_file() else {"valid": False}
    outcome = validation_outcome([result.returncode for result in results], report)
    write_json(run_dir / "candidate_status.json", outcome)
    return 0 if outcome["status"] == "CANDIDATE_SFT_ELIGIBLE" else 1


def _copy_replay_inputs(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=False)
    for name in (
        "profile.json",
        "base_dataset_config.json",
        "base_training_config.json",
        "base_unified_events.jsonl",
        "accepted_evidence.jsonl",
        "accepted_content.jsonl",
    ):
        shutil.copy2(source / name, target / name)
    shutil.copytree(source / "snapshots", target / "snapshots")


def _run_replay_once(
    run_dir: Path, profile: Mapping[str, Any], project_root: Path
) -> tuple[Path, list[int], list[int]]:
    paths = prepare_candidate_run(run_dir, profile)
    build_results = run_profile_commands(
        profile["candidate_build_commands"],
        project_root=project_root,
        run_config=paths["run_config"],
        run_training_config=paths["run_training_config"],
    )
    if any(result.returncode != 0 for result in build_results):
        diagnostics = "\n".join(
            result.stderr.strip() for result in build_results if result.stderr
        )
        raise RuntimeError(f"offline replay build failed: {diagnostics}")
    validation_results = run_profile_commands(
        profile["validation_commands"],
        project_root=project_root,
        run_config=paths["run_config"],
        run_training_config=paths["run_training_config"],
    )
    report_path = run_dir / "validation_report.json"
    if report_path.is_file():
        write_json(
            report_path,
            normalize_validation_report_paths(_read_json(report_path)),
        )
    return (
        run_dir,
        [result.returncode for result in build_results],
        [result.returncode for result in validation_results],
    )


def reproduce_run(profile_path: Path, run_id: str) -> dict[str, Any]:
    profile, project_root = _resolve_profile(profile_path)
    source_run = _run_dir(profile, project_root, run_id)
    input_errors = validate_replay_inputs(source_run)
    if input_errors:
        raise ValueError("replay inputs invalid: " + ",".join(input_errors))
    os.environ["MACRO_DATASET_OFFLINE"] = "1"
    frozen_profile = _read_json(source_run / "profile.json")
    replay_dirs = []
    runs = []
    for label in ("replay-1", "replay-2"):
        replay_dir = source_run / label
        _copy_replay_inputs(source_run, replay_dir)
        replay_dirs.append(replay_dir)
        runs.append(_run_replay_once(replay_dir, frozen_profile, project_root))
    comparison = compare_artifact_sets(
        replay_dirs[0],
        replay_dirs[1],
        (
            "candidate_master_data.jsonl",
            "candidate_sft_dataset.jsonl",
            "split_manifest.json",
            "validation_report.json",
        ),
    )
    validation_codes = [row[2] for row in runs]
    report = {
        "run_id": run_id,
        "offline": True,
        "network_accessed": False,
        "prose_regenerated": False,
        "model_loaded": False,
        "ready": all(
            all(return_code == 0 for return_code in codes)
            for codes in validation_codes
        ),
        "build_return_codes": [row[1] for row in runs],
        "validation_return_codes": validation_codes,
        **comparison,
    }
    write_json(source_run / "reproducibility_report.json", report)
    return report


def _run_reproduce(args: argparse.Namespace) -> int:
    report = reproduce_run(args.profile, args.run_id)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["stable"] else 1


def _pending_stage(args: argparse.Namespace) -> int:
    raise SystemExit(f"{args.command} is not implemented yet")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build auditable macro dataset candidates")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command, handler in (("discover", _run_discover), ("audit", _run_audit)):
        stage = subparsers.add_parser(command)
        stage.add_argument("--input", type=Path, required=True)
        stage.add_argument("--output", type=Path, required=True)
        if command == "audit":
            stage.add_argument("--policy", choices=(STRICT_POLICY,), default=None)
            stage.add_argument("--accepted-output", type=Path)
            stage.add_argument("--quarantine-output", type=Path)
            stage.add_argument("--required-event-id", action="append", default=[])
            stage.add_argument("--batch-report", type=Path)
        stage.set_defaults(handler=handler)
    for command, handler in (("build", _run_build), ("validate", _run_validate)):
        stage = subparsers.add_parser(command)
        stage.add_argument("--profile", type=Path, required=True)
        stage.add_argument("--run-id", required=True)
        stage.set_defaults(handler=handler)
    stage = subparsers.add_parser("reproduce")
    stage.add_argument("--profile", type=Path, required=True)
    stage.add_argument("--run-id", required=True)
    stage.set_defaults(handler=_run_reproduce)
    for command in ("enrich",):
        stage = subparsers.add_parser(command)
        stage.set_defaults(handler=_pending_stage)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
