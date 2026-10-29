from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping


RUN_FILES = (
    "base_unified_events.jsonl",
    "discovery_candidates.jsonl",
    "gap_manifest.jsonl",
    "search_plan.jsonl",
    "search_audit.jsonl",
    "evidence_candidates.jsonl",
    "accepted_evidence.jsonl",
    "rejected_evidence.jsonl",
    "content_candidates.jsonl",
    "accepted_content.jsonl",
    "quarantine.jsonl",
)

CAUSAL_STATUSES = {
    "NOT_IDENTIFIED",
    "DESCRIPTIVE_EVENT_STUDY",
    "QUASI_EXPERIMENTAL_CANDIDATE",
    "IDENTIFIED",
}

STRICT_POLICY = "strict-claim-closure-v2"
STRICT_SUPPORT_TYPES = {
    "DIRECT_FACT",
    "PREMISE_SUPPORT",
    "CALCULATED_LINEAGE",
    "NEGATIVE_SEARCH_AUDIT",
}
REQUIRED_HORIZONS = {"IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM"}
REQUIRED_MARKET_ENDPOINTS = {"T_MINUS_1", "T0", "D1", "D3", "D5", "D20"}
REQUIRED_QA_TYPES = {
    "EVIDENCE_QUERY",
    "MECHANISM_STAGE",
    "MARKET_VALIDATION",
    "INDUSTRY_COMPANY",
}
PLACEHOLDER_FRAGMENTS = (
    "待补充",
    "待完善",
    "占位",
    "todo",
    "tbd",
    "公告后0至1个交易日",
    "开始调整订单、套保、融资或库存决策",
)


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def classify_temporal_role(
    *, published_at: str, anchor_at: str, declared_role: str
) -> str:
    if declared_role == "POST_EVENT_VALIDATION":
        return "POST_EVENT_VALIDATION"
    if _time(published_at) > _time(anchor_at):
        return "CUTOFF_BLOCKED"
    return "AS_OF_EVIDENCE"


def evaluate_candidate_evidence(record: Mapping[str, Any]) -> dict[str, Any]:
    if record.get("statement_class") == "SOURCE_FACT" and record.get("source_tier") not in {"T1", "T2"}:
        return {"accepted": False, "reason": "SOURCE_TIER_NOT_ELIGIBLE"}
    if record.get("temporal_role") == "CUTOFF_BLOCKED":
        return {"accepted": False, "reason": "CUTOFF_BLOCKED"}
    if not all(record.get(field) for field in ("original_quote", "locator", "source_url")):
        return {"accepted": False, "reason": "SOURCE_EVIDENCE_INCOMPLETE"}
    return {"accepted": True, "reason": "GATES_PASSED"}


def validate_causal_gate(causal: Mapping[str, Any]) -> list[str]:
    status = str(causal.get("status") or "")
    allowed = causal.get("causal_attribution_allowed") is True
    conclusion = causal.get("causal_conclusion")
    gates = causal.get("gate_results") or {}
    contradiction = (
        status not in CAUSAL_STATUSES
        or (status != "IDENTIFIED" and (allowed or conclusion != "ABSTAIN"))
        or (
            status == "IDENTIFIED"
            and (not allowed or not gates or not all(value is True for value in gates.values()))
        )
    )
    return ["CAUSAL_GATE_CONTRADICTION"] if contradiction else []


def _nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _contains_placeholder(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    lowered = value.lower()
    return any(fragment in lowered for fragment in PLACEHOLDER_FRAGMENTS)


def _event_evidence(event: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    direct = event.get("evidence_registry") or []
    if direct:
        return list(direct)
    nested_event = event.get("event") or {}
    reasoning = nested_event.get("reasoning_chain") or {}
    return list(reasoning.get("evidence_registry") or [])


def _evidence_index(event: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    pools = [_event_evidence(event)]
    for company in event.get("companies") or []:
        pools.append(company.get("company_evidence") or [])
    for pool in pools:
        for evidence in pool:
            evidence_id = str(evidence.get("evidence_id") or "")
            if evidence_id:
                result[evidence_id] = evidence
    return result


def _market_errors(window: Any, prefix: str) -> set[str]:
    codes: set[str] = set()
    if not isinstance(window, Mapping) or window.get("status") != "CALCULATED":
        return {f"{prefix}_MARKET_NOT_CALCULATED"}
    endpoints = window.get("endpoints")
    if not isinstance(endpoints, Mapping) or not REQUIRED_MARKET_ENDPOINTS.issubset(endpoints):
        codes.add(f"{prefix}_MARKET_ENDPOINTS_INCOMPLETE")
        return codes
    if not _nonempty_text(window.get("data_source")):
        codes.add(f"{prefix}_MARKET_SOURCE_MISSING")
    if not _nonempty_text(window.get("formula")):
        codes.add(f"{prefix}_MARKET_FORMULA_MISSING")
    if window.get("continuous_trading_verified") is not True:
        codes.add(f"{prefix}_CONTINUOUS_TRADING_UNVERIFIED")
    for endpoint_name in REQUIRED_MARKET_ENDPOINTS:
        endpoint = endpoints.get(endpoint_name)
        if not isinstance(endpoint, Mapping):
            codes.add(f"{prefix}_MARKET_ENDPOINT_INVALID")
            continue
        if not _nonempty_text(endpoint.get("date")):
            codes.add(f"{prefix}_MARKET_DATE_MISSING")
        raw_keys = {"raw_value", "market_raw_value"}
        if prefix == "COMPANY":
            raw_keys.add("industry_raw_value")
        if any(not isinstance(endpoint.get(key), (int, float)) for key in raw_keys):
            codes.add(f"{prefix}_MARKET_RAW_VALUE_MISSING")
        result_keys = {"return", "market_return", "market_relative_return"}
        if prefix == "COMPANY":
            result_keys.update({"industry_return", "industry_relative_return"})
        if any(not isinstance(endpoint.get(key), (int, float)) for key in result_keys):
            codes.add(f"{prefix}_MARKET_RETURN_MISSING")
    baseline = endpoints.get("T_MINUS_1") or {}
    checks = (("raw_value", "return"), ("market_raw_value", "market_return"))
    if prefix == "COMPANY":
        checks += (("industry_raw_value", "industry_return"),)
    for endpoint in endpoints.values():
        if not isinstance(endpoint, Mapping):
            continue
        for raw_key, return_key in checks:
            raw_value = endpoint.get(raw_key)
            baseline_value = baseline.get(raw_key)
            recorded = endpoint.get(return_key)
            if not all(isinstance(value, (int, float)) for value in (raw_value, baseline_value, recorded)):
                continue
            if baseline_value == 0 or abs((raw_value / baseline_value - 1) - recorded) > 1e-9:
                codes.add(f"{prefix}_MARKET_FORMULA_MISMATCH")
        own_return = endpoint.get("return")
        market_return = endpoint.get("market_return")
        market_relative = endpoint.get("market_relative_return")
        if all(isinstance(value, (int, float)) for value in (own_return, market_return, market_relative)):
            if abs((own_return - market_return) - market_relative) > 1e-9:
                codes.add(f"{prefix}_MARKET_FORMULA_MISMATCH")
        if prefix == "COMPANY":
            industry_return = endpoint.get("industry_return")
            industry_relative = endpoint.get("industry_relative_return")
            if all(isinstance(value, (int, float)) for value in (own_return, industry_return, industry_relative)):
                if abs((own_return - industry_return) - industry_relative) > 1e-9:
                    codes.add("COMPANY_MARKET_FORMULA_MISMATCH")
    return codes


def strict_claim_closure_gaps(record: Mapping[str, Any]) -> list[str]:
    """Return stable fail-closed reason codes for strict-claim-closure-v2."""
    unified = record.get("unified_event") if isinstance(record.get("unified_event"), Mapping) else record
    event_id = str(unified.get("event_id") or record.get("event_id") or "")
    codes: set[str] = set()
    evidence = _evidence_index(unified)

    if not event_id:
        codes.add("EVENT_ID_MISSING")
    if unified.get("review_status") != "NEEDS_HUMAN_REVIEW":
        codes.add("REVIEW_STATUS_INVALID")
    if unified.get("formal_ready") is not False:
        codes.add("FORMAL_READY_MUST_BE_FALSE")
    codes.update(validate_causal_gate(unified.get("causal_assessment") or {}))

    event_evidence = _event_evidence(unified)
    if not event_evidence:
        codes.add("EVENT_EVIDENCE_MISSING")
    for item in event_evidence:
        if item.get("source_tier") not in {"T1", "T2"}:
            codes.add("EVENT_PRIMARY_EVIDENCE_TIER_INVALID")
        if not all(_nonempty_text(item.get(key)) for key in (
            "evidence_id", "publisher", "published_at", "retrieved_at",
            "original_quote", "locator", "source_url", "snapshot_sha256",
        )):
            codes.add("EVENT_EVIDENCE_LINEAGE_INCOMPLETE")
        if not item.get("supports_node_ids"):
            codes.add("EVIDENCE_SUPPORT_MAP_MISSING")

    industries = list(unified.get("industries") or [])
    if not 5 <= len(industries) <= 10:
        codes.add("INDUSTRY_COUNT_OUT_OF_RANGE")
    industry_ids = {str(row.get("industry_id") or "") for row in industries}
    node_ids: set[str] = set()
    industry_statements: list[tuple[str, ...]] = []
    for industry in industries:
        if industry.get("event_id") != event_id or not industry.get("industry_id"):
            codes.add("INDUSTRY_EVENT_LINK_INVALID")
        nodes = list(industry.get("mechanism_nodes") or [])
        if len(nodes) != 7:
            codes.add("INDUSTRY_MECHANISM_NOT_SEVEN_STEPS")
        normalized_statements: list[str] = []
        for node in nodes:
            node_id = str(node.get("node_id") or "")
            if not node_id or node_id in node_ids:
                codes.add("MECHANISM_NODE_ID_INVALID")
            node_ids.add(node_id)
            statement = str(node.get("statement_zh") or "").strip()
            normalized_statements.append(statement)
            if not statement or _contains_placeholder(statement):
                codes.add("MECHANISM_NODE_PLACEHOLDER_OR_GENERIC")
            support_type = node.get("support_type")
            if support_type not in STRICT_SUPPORT_TYPES:
                codes.add("MECHANISM_SUPPORT_TYPE_INVALID")
            support_ids = list(node.get("evidence_ids") or [])
            if support_type in {"DIRECT_FACT", "PREMISE_SUPPORT"}:
                if not support_ids:
                    codes.add("MECHANISM_NODE_EVIDENCE_MISSING")
                for evidence_id in support_ids:
                    item = evidence.get(str(evidence_id))
                    if not item or item.get("source_tier") not in {"T1", "T2"}:
                        codes.add("MECHANISM_NODE_PRIMARY_SUPPORT_MISSING")
                    elif node_id not in (item.get("supports_node_ids") or []):
                        codes.add("MECHANISM_EVIDENCE_REVERSE_LINK_MISSING")
                if not _nonempty_text(node.get("support_rationale_zh")):
                    codes.add("MECHANISM_SUPPORT_RATIONALE_MISSING")
                if not _nonempty_text(node.get("evidence_locator")):
                    codes.add("MECHANISM_EVIDENCE_LOCATOR_MISSING")
            elif support_type == "CALCULATED_LINEAGE":
                codes.update(_market_errors(industry.get("market_window"), "INDUSTRY"))
            elif support_type == "NEGATIVE_SEARCH_AUDIT":
                audit = node.get("negative_search_audit")
                if not isinstance(audit, Mapping) or not all(
                    key in audit for key in ("query", "window_start", "window_end", "result_count", "documents_reviewed")
                ):
                    codes.add("NEGATIVE_SEARCH_AUDIT_INCOMPLETE")
        industry_statements.append(tuple(normalized_statements))
        horizons = industry.get("horizon_analysis") or {}
        if set(horizons) != REQUIRED_HORIZONS or len(set(horizons.values())) != 3:
            codes.add("INDUSTRY_HORIZONS_NOT_DISTINCT")
        if any(not _nonempty_text(horizons.get(key)) or _contains_placeholder(horizons.get(key)) for key in REQUIRED_HORIZONS):
            codes.add("INDUSTRY_HORIZON_PLACEHOLDER")
        codes.update(_market_errors(industry.get("market_window"), "INDUSTRY"))
    if len(industries) > 1 and len(set(industry_statements)) != len(industry_statements):
        codes.add("GENERIC_INDUSTRY_TEMPLATE_REUSED")

    companies = list(unified.get("companies") or [])
    expected_company_count = len(industries) * 3
    if len(companies) != expected_company_count:
        codes.add("COMPANY_COUNT_NOT_THREE_PER_INDUSTRY")
    per_industry: dict[str, int] = {}
    company_ids: set[str] = set()
    for company in companies:
        industry_id = str(company.get("industry_id") or "")
        per_industry[industry_id] = per_industry.get(industry_id, 0) + 1
        mapping_id = str(company.get("mapping_id") or "")
        if mapping_id:
            company_ids.add(mapping_id)
        if company.get("event_id") != event_id or industry_id not in industry_ids:
            codes.add("COMPANY_EVENT_INDUSTRY_LINK_INVALID")
        disclosures = [
            item for item in company.get("company_evidence") or []
            if item.get("source_tier") in {"T1", "T2"}
            and item.get("temporal_role") == "AS_OF_EVIDENCE"
            and all(_nonempty_text(item.get(key)) for key in ("original_quote", "locator", "source_url", "published_at"))
        ]
        if len({item.get("evidence_id") for item in disclosures}) < 2:
            codes.add("COMPANY_PRE_EVENT_DISCLOSURES_LT_TWO")
        horizons = company.get("horizon_analysis") or {}
        if set(horizons) != REQUIRED_HORIZONS or len(set(horizons.values())) != 3:
            codes.add("COMPANY_HORIZONS_NOT_DISTINCT")
        if not _nonempty_text(company.get("business_exposure_zh")):
            codes.add("COMPANY_EXPOSURE_MISSING")
        if not company.get("confounders") or not company.get("counterevidence"):
            codes.add("COMPANY_CONFOUNDERS_OR_COUNTEREVIDENCE_MISSING")
        codes.update(_market_errors(company.get("market_window"), "COMPANY"))
    if any(per_industry.get(industry_id) != 3 for industry_id in industry_ids):
        codes.add("COMPANY_COUNT_NOT_THREE_PER_INDUSTRY")

    qa = list(unified.get("qa") or [])
    qa_types = {str(row.get("qa_type") or "") for row in qa}
    if not REQUIRED_QA_TYPES.issubset(qa_types):
        codes.add("QA_TYPES_INCOMPLETE")
    valid_refs = {event_id, *evidence, *industry_ids, *node_ids, *company_ids}
    for item in qa:
        if item.get("event_id") != event_id or not _nonempty_text(item.get("direct_answer_zh")):
            codes.add("QA_DIRECT_ANSWER_OR_EVENT_LINK_MISSING")
        refs = list(item.get("reference_ids") or [])
        if not refs or any(str(ref) not in valid_refs for ref in refs):
            codes.add("QA_DANGLING_REFERENCE")
        if not item.get("evidence_ids") or any(str(ref) not in evidence for ref in item.get("evidence_ids") or []):
            codes.add("QA_EVIDENCE_REFERENCE_INVALID")

    if record.get("closure_status") == "CLOSED" and codes:
        codes.add("FALSE_CLOSED_STATUS")
    return sorted(codes)


def canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ) + "\n"


def canonical_sha256(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def candidate_eligibility(
    record: Mapping[str, Any], *, policy: str | None = None
) -> bool:
    if policy == STRICT_POLICY:
        return not strict_claim_closure_gaps(record)
    return (
        record.get("closure_status") == "CLOSED"
        and not record.get("errors")
        and not record.get("warnings")
    )


def partition_candidates(
    records: list[Mapping[str, Any]],
    *,
    policy: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    eligible, quarantine = [], []
    for record in sorted(records, key=lambda row: str(row.get("event_id"))):
        strict_reasons = strict_claim_closure_gaps(record) if policy == STRICT_POLICY else []
        if candidate_eligibility(record, policy=policy):
            eligible.append(dict(record))
            continue
        reasons = []
        if record.get("closure_status") != "CLOSED":
            reasons.append(str(record.get("closure_status") or "UNKNOWN_CLOSURE"))
        reasons.extend(str(value) for value in record.get("errors") or [])
        reasons.extend(str(value) for value in record.get("warnings") or [])
        reasons.extend(strict_reasons)
        quarantine.append(
            {
                "event_id": str(record.get("event_id") or ""),
                "quarantine_reasons": sorted(set(reasons)),
            }
        )
    return eligible, quarantine


def validate_atomic_batch(
    accepted_records: list[Mapping[str, Any]], required_event_ids: list[str]
) -> list[str]:
    accepted_ids = {str(record.get("event_id") or "") for record in accepted_records}
    required_ids = set(required_event_ids)
    codes = []
    if accepted_ids != required_ids:
        codes.append("ATOMIC_BATCH_EVENT_SET_INCOMPLETE")
    if len(accepted_ids) != len(accepted_records):
        codes.append("ATOMIC_BATCH_DUPLICATE_EVENT_ID")
    return codes


def assemble_candidate_master(
    base_events: list[Mapping[str, Any]],
    accepted_content: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for event in base_events:
        event_id = str(event.get("event_id") or "")
        if not event_id or event_id in by_id:
            raise ValueError("base events require unique non-empty event_id")
        by_id[event_id] = dict(event)

    accepted_ids: set[str] = set()
    for record in sorted(accepted_content, key=lambda row: str(row.get("event_id") or "")):
        event_id = str(record.get("event_id") or "")
        unified_event = record.get("unified_event")
        if record.get("operation") != "UPSERT":
            raise ValueError(f"unsupported content operation for {event_id}")
        if event_id in accepted_ids:
            raise ValueError(f"duplicate accepted content for {event_id}")
        if not isinstance(unified_event, dict) or unified_event.get("event_id") != event_id:
            raise ValueError(f"unified event mismatch for {event_id}")
        if not record.get("evidence_ids"):
            raise ValueError(f"accepted content lacks evidence_ids for {event_id}")
        if record.get("content_sha256") != canonical_sha256(unified_event):
            raise ValueError(f"content SHA mismatch for {event_id}")
        accepted_ids.add(event_id)
        by_id[event_id] = dict(unified_event)
    return [by_id[event_id] for event_id in sorted(by_id)]


def _existing_split_index(splits: Mapping[str, list[str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for split_name in ("train", "validation", "test"):
        for event_id in splits.get(split_name, []):
            if event_id in result:
                raise ValueError(f"event appears in multiple splits: {event_id}")
            result[event_id] = split_name
    return result


def _stable_split(event_id: str, policy: Mapping[str, Any]) -> str:
    if policy.get("method") != "sha256_mod_100":
        raise ValueError("unsupported split method")
    raw = f'{policy["version"]}:{event_id}'.encode("utf-8")
    bucket = int(sha256(raw).hexdigest()[:8], 16) % 100
    if bucket <= int(policy["train_max"]):
        return "train"
    if bucket <= int(policy["validation_max"]):
        return "validation"
    return "test"


def build_event_splits(
    event_ids: list[str],
    base_splits: Mapping[str, list[str]],
    accepted_content: list[Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> dict[str, list[str]]:
    existing = _existing_split_index(base_splits)
    overrides = {
        str(row["event_id"]): row.get("split_assignment")
        for row in accepted_content
        if row.get("split_assignment") is not None
    }
    output: dict[str, list[str]] = {"train": [], "validation": [], "test": []}
    for event_id in sorted(event_ids):
        split_name = existing.get(event_id)
        if split_name is None:
            split_name = overrides.get(event_id) or _stable_split(event_id, policy)
        if split_name not in output:
            raise ValueError(f"invalid split for {event_id}: {split_name}")
        output[split_name].append(event_id)
    return output


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def sha256_path(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compare_artifact_sets(
    left: Path, right: Path, names: tuple[str, ...] | list[str]
) -> dict[str, Any]:
    artifacts = []
    for name in names:
        left_hash = sha256_path(left / name)
        right_hash = sha256_path(right / name)
        artifacts.append(
            {
                "name": name,
                "left_sha256": left_hash,
                "right_sha256": right_hash,
                "matches": left_hash == right_hash,
            }
        )
    return {"stable": all(row["matches"] for row in artifacts), "artifacts": artifacts}


def validate_replay_inputs(run_dir: Path) -> list[str]:
    required = {
        "profile.json": "PROFILE_MISSING",
        "base_dataset_config.json": "BASE_DATASET_CONFIG_MISSING",
        "base_training_config.json": "BASE_TRAINING_CONFIG_MISSING",
        "base_unified_events.jsonl": "BASE_UNIFIED_EVENTS_MISSING",
        "accepted_evidence.jsonl": "ACCEPTED_EVIDENCE_MISSING",
        "accepted_content.jsonl": "ACCEPTED_CONTENT_MISSING",
    }
    errors = [
        code for name, code in required.items() if not (run_dir / name).is_file()
    ]
    if not (run_dir / "snapshots").is_dir():
        errors.append("SNAPSHOT_DIRECTORY_MISSING")
    return sorted(errors)


def init_run(root: Path, *, run_id: str, request: Mapping[str, Any]) -> Path:
    run_dir = root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "snapshots").mkdir()
    write_json(run_dir / "request.json", {**dict(request), "run_id": run_id})
    for name in RUN_FILES:
        (run_dir / name).write_text("", encoding="utf-8", newline="\n")
    return run_dir
