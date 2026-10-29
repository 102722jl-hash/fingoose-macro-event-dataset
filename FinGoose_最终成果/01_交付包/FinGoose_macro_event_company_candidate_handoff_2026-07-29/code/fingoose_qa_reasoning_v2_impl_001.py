"""Build auditable research Q&A records from the existing ten-event workbench."""

from __future__ import annotations

import calendar
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from fingoose_company_impact_ui_v2 import build_ui_bundle
from fingoose_qa_contract_v2 import TASK_TYPES, load_event_profiles


ANSWER_LAYER_KEYS = (
    "SOURCE_FACTS",
    "RESEARCH_INFERENCE",
    "CALCULATED_FACTS",
    "REFUSAL_AND_BOUNDARIES",
)
WINDOW_KEYS = ("T_MINUS_1", "T0", "D1", "D3", "D5", "D20")
HORIZON_KEYS = ("IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM")
TASK_LABELS = {
    "MAIN_REASONING": "综合研判",
    "EVIDENCE_AUDIT": "证据核查",
    "MARKET_VALIDATION": "行情验证",
    "INDUSTRY_COMPANY": "行业—公司",
}
EXPECTED_INDUSTRY_COUNTS = {
    "event-01": 8,
    "event-02": 8,
    "event-03": 8,
    "event-04": 8,
    "event-05": 7,
    "event-06": 7,
    "event-07": 7,
    "event-08": 7,
    "event-09": 8,
    "event-10": 9,
}
HIDDEN_FIELDS = (
    "expected_industry_mapping_ids",
    "expected_evidence_ids",
    "expected_market_window_ids",
    "hard_failure_labels",
)


@dataclass(frozen=True)
class QaBundle:
    cases: list[dict[str, Any]]
    answers: list[dict[str, Any]]
    labels: list[dict[str, Any]]


def _parse_boundary(value: str) -> datetime:
    text = str(value).strip()
    if len(text) == 7:
        year, month = (int(part) for part in text.split("-"))
        day = calendar.monthrange(year, month)[1]
        return datetime.combine(datetime(year, month, day).date(), time.max, timezone.utc)
    if len(text) == 10:
        return datetime.combine(datetime.fromisoformat(text).date(), time.max, timezone.utc)
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _eligible(first_public_at: Any, cutoff_at: str) -> bool:
    if not first_public_at:
        return False
    try:
        return _parse_boundary(str(first_public_at)) <= _parse_boundary(cutoff_at)
    except (TypeError, ValueError):
        return False


def _file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _snapshot_details(
    root: Path, event_id: str, raw_path: str | None
) -> tuple[str | None, str | None]:
    if not raw_path:
        return None, None
    relative = Path(raw_path)
    candidates = [root / relative]
    if event_id == "event-01":
        candidates.append(root / "work/event_01_industry_closure_v2_candidate" / relative)
    else:
        candidates.append(root / "work/ten_event_industry_closure_v2_candidate" / relative)
    for candidate in candidates:
        sha = _file_sha256(candidate)
        if sha:
            try:
                public_path = candidate.relative_to(root).as_posix()
            except ValueError:
                public_path = candidate.as_posix()
            return public_path, sha
    return relative.as_posix(), None


def _public_evidence(
    root: Path,
    event_id: str,
    source: Mapping[str, Any],
    *,
    first_public_at: str,
) -> dict[str, Any] | None:
    url = source.get("source_url") or source.get("url")
    quote = source.get("original_quote") or source.get("quote")
    locator = source.get("locator") or source.get("evidence_locator")
    source_id = source.get("evidence_id") or source.get("source_id")
    if not all((url, quote, locator, source_id)):
        return None
    raw_path = source.get("raw_snapshot_path") or source.get("snapshot_path")
    snapshot_path, calculated_sha = _snapshot_details(
        root, event_id, str(raw_path) if raw_path else None
    )
    return {
        "evidence_id": str(source_id),
        "publisher": source.get("publisher"),
        "title": source.get("title"),
        "original_quote": str(quote),
        "locator": str(locator),
        "source_url": str(url),
        "first_public_at": first_public_at,
        "source_tier": source.get("source_tier"),
        "snapshot_path": snapshot_path,
        "snapshot_sha256": source.get("snapshot_sha256")
        or source.get("sha256")
        or calculated_sha,
    }


def _collect_evidence(
    root: Path, event: Mapping[str, Any], cutoff_at: str
) -> list[dict[str, Any]]:
    event_id = str(event["event_id"])
    rows: dict[str, dict[str, Any]] = {}
    for node in event.get("timeline") or []:
        first_public_at = str(node.get("first_public_at") or "")
        if not _eligible(first_public_at, cutoff_at):
            continue
        for source in node.get("evidence") or []:
            projected = _public_evidence(
                root, event_id, source, first_public_at=first_public_at
            )
            if projected:
                rows.setdefault(projected["evidence_id"], projected)
    for source in event.get("industry_evidence") or []:
        first_public_at = str(source.get("first_public_at") or "")
        if not _eligible(first_public_at, cutoff_at):
            continue
        projected = _public_evidence(
            root, event_id, source, first_public_at=first_public_at
        )
        if projected:
            rows.setdefault(projected["evidence_id"], projected)
    return [rows[key] for key in sorted(rows)]


def _public_chain(event: Mapping[str, Any]) -> list[dict[str, Any]]:
    impacts = list(event.get("industry_impacts") or [])
    impacts.sort(
        key=lambda row: (
            0 if row.get("impact_tier") == "CORE_DIRECT" else 1,
            str(row.get("sw1_id")),
        )
    )
    for impact in impacts:
        nodes = (impact.get("mechanism_chain") or {}).get("nodes") or []
        if len(nodes) == 7:
            return [
                {
                    "step": index,
                    "node_type": node.get("node_type"),
                    "statement_zh": node.get("statement_zh") or node.get("statement"),
                    "condition_zh": node.get("condition_zh"),
                    "invalidation_zh": node.get("invalidation_zh"),
                    "evidence_ids": list(node.get("evidence_ids") or []),
                }
                for index, node in enumerate(nodes, 1)
            ]
    raise ValueError(f"MISSING_SEVEN_STEP_CHAIN:{event['event_id']}")


def _public_impacts(event: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "event_industry_mapping_id": row["event_industry_mapping_id"],
            "sw1_id": row.get("sw1_id"),
            "industry_name_zh": row.get("display_name_zh") or row.get("sw1_name_at_event"),
            "impact_tier": row.get("impact_tier"),
            "behavior_change_zh": row.get("behavior_change_zh"),
            "observable_driver_zh": row.get("observable_driver_zh"),
            "industry_operating_variable_zh": row.get("industry_operating_variable_zh"),
            "industry_financial_variable_zh": row.get("industry_financial_variable_zh"),
            "horizon_directions": dict(row.get("horizon_directions") or {}),
            "condition_zh": row.get("condition_zh"),
            "invalidation_condition_zh": row.get("invalidation_condition_zh"),
            "counterevidence_zh": row.get("counterevidence_zh"),
            "completion_status": (row.get("completion") or {}).get("completion_status"),
            "company_count": row.get("company_count", 0),
        }
        for row in event.get("industry_impacts") or []
    ]


def _fixed_window(source: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not source:
        return None
    return {
        "actual_date": source.get("actual_date"),
        "industry_value": source.get("industry_value"),
        "market_value": source.get("market_value"),
        "industry_return": source.get("industry_return"),
        "market_return": source.get("market_return"),
        "market_relative_return": source.get("market_relative_return"),
        "formula": source.get("formula"),
        "formula_inputs": dict(source.get("formula_inputs") or {}),
    }


def _public_market_windows(event: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for impact in event.get("industry_impacts") or []:
        window = impact.get("market_window") or {}
        fixed = window.get("fixed_windows") or {}
        rows.append(
            {
                "event_industry_mapping_id": impact["event_industry_mapping_id"],
                "industry_name_zh": impact.get("display_name_zh")
                or impact.get("sw1_name_at_event"),
                "window_status": window.get("window_status") or "UNAVAILABLE",
                "missing_value_policy": window.get("missing_value_policy")
                or "KEEP_NULL_NEVER_ZERO_IMPUTE",
                "fixed_windows": {
                    key: _fixed_window(fixed.get(key)) for key in WINDOW_KEYS
                },
            }
        )
    return rows


def _horizon_summary(impacts: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    summary: dict[str, str] = {}
    rows = list(impacts)
    for horizon in HORIZON_KEYS:
        directions = {
            str((row.get("horizon_directions") or {}).get(horizon))
            for row in rows
            if (row.get("horizon_directions") or {}).get(horizon)
        }
        summary[horizon] = next(iter(directions)) if len(directions) == 1 else "MIXED"
    return summary


def _refusals(
    event: Mapping[str, Any], profile: Mapping[str, Any]
) -> list[dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}

    def add(scope_id: str, reason: str) -> None:
        rows[scope_id] = {
            "scope_id": scope_id,
            "direction": "UNKNOWN",
            "decision": "ABSTAIN",
            "refusal_reason": reason,
        }

    anchor = next(
        (
            row
            for row in event.get("timeline") or []
            if row.get("fast_node_id") == profile.get("anchor_node_id")
        ),
        None,
    )
    if anchor and not _eligible(anchor.get("first_public_at"), profile["prediction_cutoff_at"]):
        add(str(profile["anchor_node_id"]), "ANCHOR_POST_CUTOFF")
    for impact in event.get("industry_impacts") or []:
        completion = (impact.get("completion") or {}).get("completion_status")
        if completion == "OPEN":
            add(str(impact["event_industry_mapping_id"]), "INDUSTRY_CLOSURE_OPEN")
    for company in event.get("companies") or []:
        mapping_id = str(company["mapping_id"])
        completion = (company.get("completion") or {}).get("completion_status")
        if completion == "OPEN":
            add(mapping_id, "COMPANY_CLOSURE_OPEN")
        grade = str((company.get("confounders") or {}).get("overall_grade") or "")
        if grade in {"MATERIAL", "DOMINANT", "UNRESOLVED"}:
            add(mapping_id, f"CONFOUNDER_{grade}")
        trading = company.get("trading_status_review") or {}
        if trading.get("suspension_status") in {None, "UNVERIFIED"}:
            add(mapping_id, "TRADING_STATUS_UNVERIFIED")
    return [rows[key] for key in sorted(rows)]


def _task_result(
    task_type: str,
    event: Mapping[str, Any],
    impacts: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    windows: list[dict[str, Any]],
    refusals: list[dict[str, str]],
) -> str:
    if task_type == "EVIDENCE_AUDIT":
        hashed = sum(bool(row.get("snapshot_sha256")) for row in evidence)
        return f"截止日前纳入 {len(evidence)} 条可定位来源，其中 {hashed} 条带快照哈希；无哈希材料不提升为正式事实。"
    if task_type == "MARKET_VALIDATION":
        available = sum(row["window_status"] == "AVAILABLE" for row in windows)
        return f"复核 {len(windows)} 个行业窗口，其中 {available} 个可复算；行情只作机制一致性检验，不单独证明因果。"
    if task_type == "INDUSTRY_COMPANY":
        companies = "、".join(str(row.get("company_name")) for row in event.get("companies") or [])
        return f"行业层保留 {len(impacts)} 条映射；公司样本为 {companies}。存在 {len(refusals)} 个需拒答或待人工关闭的范围。"
    counts = {
        tier: sum(row["impact_tier"] == tier for row in impacts)
        for tier in ("CORE_DIRECT", "SECOND_ORDER", "CONDITIONAL")
    }
    return (
        f"当前候选研判覆盖 {len(impacts)} 个行业：直接影响 {counts['CORE_DIRECT']} 个、"
        f"二阶传导 {counts['SECOND_ORDER']} 个、条件性影响 {counts['CONDITIONAL']} 个。"
    )


def _make_case(profile: Mapping[str, Any], task_type: str) -> dict[str, Any]:
    event_id = str(profile["event_id"])
    slug = task_type.lower().replace("_", "-")
    return {
        "case_id": f"qa-{event_id}-{slug}",
        "event_id": event_id,
        "event_title_zh": profile["title_zh"],
        "task_type": task_type,
        "task_label_zh": TASK_LABELS[task_type],
        "question_zh": profile["questions"][task_type],
        "prediction_cutoff_at": profile["prediction_cutoff_at"],
        "anchor_node_id": profile["anchor_node_id"],
        "status": "PROPOSED",
        "review_status": "NEEDS_HUMAN_REVIEW",
        "formal_ready": False,
        "sha_gate": "DEFERRED",
    }


def _make_answer(
    root: Path,
    event: Mapping[str, Any],
    profile: Mapping[str, Any],
    case: Mapping[str, Any],
) -> dict[str, Any]:
    evidence = _collect_evidence(root, event, str(profile["prediction_cutoff_at"]))
    impacts = _public_impacts(event)
    windows = _public_market_windows(event)
    chain = _public_chain(event)
    refusals = _refusals(event, profile)
    horizon = _horizon_summary(impacts)
    source_summary = (
        f"本答案只使用 {profile['prediction_cutoff_at']} 之前公开且带原文定位的信息；"
        f"共列示 {len(evidence)} 条公开证据。"
    )
    inference_summary = _task_result(
        str(case["task_type"]), event, impacts, evidence, windows, refusals
    )
    calculated_summary = (
        "固定窗口以 T-1 为基期，行业相对收益 = 行业收益 - 沪深300收益；"
        "缺失值保持为空，不补零。"
    )
    boundary_summary = (
        "所有方向均为待人工复核的研究候选，不构成买卖建议；"
        "缺证、截止日后信息、未关闭行业或公司范围一律输出 UNKNOWN + ABSTAIN。"
    )
    return {
        "case_id": case["case_id"],
        "event_id": case["event_id"],
        "event_title_zh": case["event_title_zh"],
        "task_type": case["task_type"],
        "task_label_zh": case["task_label_zh"],
        "prediction_cutoff_at": case["prediction_cutoff_at"],
        "answer_focus_zh": inference_summary,
        "answer_layers": {
            "SOURCE_FACTS": {
                "summary_zh": source_summary,
                "evidence": evidence,
            },
            "RESEARCH_INFERENCE": {
                "summary_zh": inference_summary,
                "mechanism_chain": chain,
                "industry_impacts": impacts,
                "horizon_summary": horizon,
            },
            "CALCULATED_FACTS": {
                "summary_zh": calculated_summary,
                "market_windows": windows,
            },
            "REFUSAL_AND_BOUNDARIES": {
                "summary_zh": boundary_summary,
                "refusals": refusals,
            },
        },
        "evidence": evidence,
        "mechanism_chain": chain,
        "industry_impacts": impacts,
        "horizon_summary": horizon,
        "market_windows": windows,
        "refusals": refusals,
        "status": "PROPOSED",
        "review_status": "NEEDS_HUMAN_REVIEW",
        "formal_ready": False,
        "sha_gate": "DEFERRED",
        "investment_advice": "NOT_PROVIDED",
    }


def build_qa_records(root: Path) -> QaBundle:
    root = root.resolve()
    profiles = load_event_profiles(root / "configs/qa_reasoning_v2/qa_event_profiles.json")
    workbench = build_ui_bundle(root)
    events = {str(row["event_id"]): row for row in workbench["events"]}
    cases: list[dict[str, Any]] = []
    answers: list[dict[str, Any]] = []
    labels: list[dict[str, Any]] = []
    for profile in profiles:
        event = events[str(profile["event_id"])]
        for task_type in TASK_TYPES:
            case = _make_case(profile, task_type)
            answer = _make_answer(root, event, profile, case)
            label = {
                "case_id": case["case_id"],
                "event_id": case["event_id"],
                "task_type": task_type,
                "expected_industry_mapping_ids": [
                    row["event_industry_mapping_id"]
                    for row in answer["industry_impacts"]
                ],
                "expected_evidence_ids": [
                    row["evidence_id"] for row in answer["evidence"]
                ],
                "expected_market_window_ids": [
                    row["event_industry_mapping_id"]
                    for row in answer["market_windows"]
                ],
                "required_abstentions": [
                    row["scope_id"] for row in answer["refusals"]
                ],
                "hard_failure_labels": [],
                "answer_status": "PROPOSED",
                "review_status": "NEEDS_HUMAN_REVIEW",
            }
            cases.append(case)
            answers.append(answer)
            labels.append(label)
    key = lambda row: str(row["case_id"])
    return QaBundle(
        cases=sorted(cases, key=key),
        answers=sorted(answers, key=key),
        labels=sorted(labels, key=key),
    )


def validate_qa_bundle(bundle: QaBundle) -> dict[str, Any]:
    failures: list[str] = []
    case_ids = [str(row["case_id"]) for row in bundle.cases]
    answer_by_id = {str(row["case_id"]): row for row in bundle.answers}
    label_by_id = {str(row["case_id"]): row for row in bundle.labels}
    if len(case_ids) != 40 or len(set(case_ids)) != 40:
        failures.append("QA_CASE_COUNT_OR_UNIQUENESS")
    if set(case_ids) != set(answer_by_id) or set(case_ids) != set(label_by_id):
        failures.append("QA_PUBLIC_HIDDEN_JOIN_MISMATCH")
    public_text = json.dumps([bundle.cases, bundle.answers], ensure_ascii=False)
    if any(field in public_text for field in HIDDEN_FIELDS):
        failures.append("PUBLIC_HIDDEN_LABEL_LEAKAGE")
    max_error = 0.0
    required_abstention_count = 0
    event_counts: dict[str, int] = {}
    for case_id in case_ids:
        answer = answer_by_id[case_id]
        label = label_by_id[case_id]
        if list(answer.get("answer_layers") or {}) != list(ANSWER_LAYER_KEYS):
            failures.append(f"ANSWER_LAYER_MISMATCH:{case_id}")
        if len(answer.get("mechanism_chain") or []) != 7:
            failures.append(f"MECHANISM_CHAIN_LENGTH:{case_id}")
        if set(answer.get("horizon_summary") or {}) != set(HORIZON_KEYS):
            failures.append(f"HORIZON_CONTRACT:{case_id}")
        if (
            answer.get("status") != "PROPOSED"
            or answer.get("review_status") != "NEEDS_HUMAN_REVIEW"
            or answer.get("formal_ready") is not False
            or answer.get("sha_gate") != "DEFERRED"
        ):
            failures.append(f"INVALID_RELEASE_STATE:{case_id}")
        if answer.get("task_type") == "MAIN_REASONING":
            event_counts[str(answer["event_id"])] = len(answer["industry_impacts"])
        refusal_scopes = {row["scope_id"] for row in answer.get("refusals") or []}
        required = set(label.get("required_abstentions") or [])
        required_abstention_count += len(required)
        if not required.issubset(refusal_scopes):
            failures.append(f"MISSING_REQUIRED_ABSTENTION:{case_id}")
        for window in answer.get("market_windows") or []:
            if list(window.get("fixed_windows") or {}) != list(WINDOW_KEYS):
                failures.append(f"MARKET_WINDOW_CONTRACT:{case_id}")
            for point in (window.get("fixed_windows") or {}).values():
                if not point:
                    continue
                inputs = point.get("formula_inputs") or {}
                actual = point.get("market_relative_return")
                required_inputs = (
                    "industry_T_MINUS_1",
                    "industry_value",
                    "market_T_MINUS_1",
                    "market_value",
                )
                if actual is None or not all(inputs.get(key) is not None for key in required_inputs):
                    continue
                expected = (
                    float(inputs["industry_value"])
                    / float(inputs["industry_T_MINUS_1"])
                    - 1.0
                ) - (
                    float(inputs["market_value"])
                    / float(inputs["market_T_MINUS_1"])
                    - 1.0
                )
                max_error = max(max_error, abs(expected - float(actual)))
    if event_counts != EXPECTED_INDUSTRY_COUNTS:
        failures.append("INDUSTRY_EVENT_COUNTS_MISMATCH")
    if max_error > 1e-10:
        failures.append("MARKET_FORMULA_MISMATCH")
    return {
        "event_count": len({row["event_id"] for row in bundle.cases}),
        "case_count": len(bundle.cases),
        "answer_count": len(bundle.answers),
        "label_count": len(bundle.labels),
        "required_abstention_count": required_abstention_count,
        "market_formula_max_abs_error": max_error,
        "hard_failures": sorted(set(failures)),
        "status": "PROPOSED",
        "review_status": "NEEDS_HUMAN_REVIEW",
        "formal_ready": False,
        "sha_gate": "DEFERRED",
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def load_existing_source_fetches(root: Path) -> list[dict[str, Any]]:
    locations = (
        ("event-01", root / "work/event_01_industry_closure_v2_candidate"),
        (None, root / "work/ten_event_industry_closure_v2_candidate"),
    )
    rows: dict[str, dict[str, Any]] = {}
    for forced_event_id, source_root in locations:
        for source in read_jsonl(source_root / "industry_source_fetches.jsonl"):
            row = dict(source)
            if forced_event_id:
                row["event_id"] = forced_event_id
            raw_path = row.get("raw_snapshot_path")
            if raw_path:
                snapshot = source_root / str(raw_path)
                row["snapshot_path"] = snapshot.relative_to(root).as_posix()
                row["snapshot_sha256"] = _file_sha256(snapshot)
            else:
                row["snapshot_path"] = None
                row["snapshot_sha256"] = None
            rows[str(row["source_id"])] = row
    return [rows[key] for key in sorted(rows)]


def write_candidate_package(
    root: Path,
    output_root: Path,
    bundle: QaBundle,
    *,
    source_fetches: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    report = validate_qa_bundle(bundle)
    write_jsonl(output_root / "qa_cases.jsonl", bundle.cases)
    write_jsonl(output_root / "qa_answer_candidates.jsonl", bundle.answers)
    write_jsonl(output_root / "evaluator_only/qa_labels.jsonl", bundle.labels)
    write_jsonl(
        output_root / "source_fetches.jsonl",
        source_fetches if source_fetches is not None else load_existing_source_fetches(root),
    )
    (output_root / "qa_validation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    artifact_paths = (
        "qa_cases.jsonl",
        "qa_answer_candidates.jsonl",
        "source_fetches.jsonl",
        "qa_validation_report.json",
        "evaluator_only/qa_labels.jsonl",
    )
    artifacts = []
    for relative in artifact_paths:
        path = output_root / relative
        records = (
            len([line for line in path.read_text(encoding="utf-8").splitlines() if line])
            if path.suffix == ".jsonl"
            else 1
        )
        artifacts.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "records": records,
                "sha256": _file_sha256(path),
            }
        )
    manifest = {
        "dataset_version": "fingoose-event-qa-reasoning-v2-candidate",
        "event_count": report["event_count"],
        "case_count": report["case_count"],
        "answer_count": report["answer_count"],
        "label_count": report["label_count"],
        "artifacts": artifacts,
        "status": "PROPOSED",
        "review_status": "NEEDS_HUMAN_REVIEW",
        "formal_ready": False,
        "sha_gate": "DEFERRED",
    }
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


__all__ = [
    "ANSWER_LAYER_KEYS",
    "HORIZON_KEYS",
    "QaBundle",
    "TASK_LABELS",
    "TASK_TYPES",
    "WINDOW_KEYS",
    "build_qa_records",
    "load_existing_source_fetches",
    "read_jsonl",
    "validate_qa_bundle",
    "write_candidate_package",
    "write_jsonl",
]
