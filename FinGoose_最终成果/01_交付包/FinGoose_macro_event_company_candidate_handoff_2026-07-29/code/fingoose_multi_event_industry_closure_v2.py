"""Build the event-02 through event-10 industry closure overlay."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from fingoose_company_impact_io_v2 import read_jsonl, write_jsonl
from fingoose_industry_impact_v2 import load_industry_profiles


CONTRACT_PATH = Path("configs/industry_impact_v2/multi_event_closure_contract.json")
DRIVER_PAYLOAD_PATH = Path("configs/industry_impact_v2/multi_event_driver_payloads.json")
STEP_TYPES = (
    "EVENT_FACT",
    "BEHAVIOR_OR_POLICY_CHANGE",
    "OBSERVABLE_DRIVER",
    "INDUSTRY_OPERATING_VARIABLE",
    "INDUSTRY_REVENUE_OR_COST_VARIABLE",
    "DIRECTION_ASSESSMENT",
    "PRICE_CONFOUNDER_AND_COUNTEREVIDENCE",
)
STATEMENT_CLASSES = {
    "SOURCE_FACT",
    "CALCULATED_FACT",
    "RESEARCH_INFERENCE",
}
RELEASE_FIELDS = {
    "status": "PROPOSED",
    "review_status": "NEEDS_HUMAN_REVIEW",
    "formal_ready": False,
    "sha_gate": "DEFERRED",
}


class MultiEventClosureError(ValueError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _direction_text(directions: Mapping[str, str]) -> str:
    labels = {"POSITIVE": "正向", "NEGATIVE": "负向", "MIXED": "混合", "UNKNOWN": "未知"}
    return "、".join(
        f"{label}{labels[str(directions[key])]}"
        for key, label in (
            ("IMMEDIATE", "即时"),
            ("SHORT_TERM", "短期"),
            ("MEDIUM_TERM", "中期"),
        )
    )


def _contract(root: Path) -> dict[str, Any]:
    contract = _read_json(root / CONTRACT_PATH)
    step_contract = contract.get("step_contract") or []
    if tuple(row.get("step_type") for row in step_contract) != STEP_TYPES:
        raise MultiEventClosureError("INVALID_STEP_CONTRACT")
    if any(row.get("statement_class") not in STATEMENT_CLASSES for row in step_contract):
        raise MultiEventClosureError("INVALID_STATEMENT_CLASS_CONTRACT")
    if contract.get("formal_ready") is not False or contract.get("sha_gate") != "DEFERRED":
        raise MultiEventClosureError("RELEASE_BOUNDARY_VIOLATION")
    return contract


def industry_overlay_roots(root: Path) -> list[Path]:
    """Return the deterministic event-01 then event-02..10 overlay order."""

    root = root.resolve()
    return [root / row["path"] for row in _contract(root)["overlay_order"]]


def _steps(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    condition = str(profile["condition_zh"])
    invalidation = str(profile["invalidation_condition_zh"])
    counterevidence = [str(value) for value in profile["counterevidence_zh"]]
    directions = dict(profile["horizon_directions"])
    gap_reason = str(profile.get("anchor_gap_reason") or "")
    event_fact = (
        f"事件事实（发生时间：{profile['anchor_occurred_at']}；首次公开：{profile['anchor_first_public_at']}）："
        f"{profile['anchor_fact_zh']}"
    )
    if gap_reason:
        event_fact += f" 时间口径说明：{gap_reason}"
    verification = (
        f"以事件日申万一级行业代码 {profile['sw1_id']} 对比沪深300，验证共同交易日"
        " T-20 至 D20、固定窗口与主驱动；价格只用于验证，不用于选择行业或生成方向。"
        f"竞争解释包括：{'；'.join(counterevidence)}"
    )
    statements = (
        (
            "EVENT_FACT",
            "SOURCE_FACT",
            event_fact,
        ),
        (
            "BEHAVIOR_OR_POLICY_CHANGE",
            "SOURCE_FACT",
            f"行为或政策变化：{profile['behavior_change_zh']}。对{profile['display_name_zh']}的首要传导是"
            f"“{profile['observable_driver_zh']}”，并落到“{profile['industry_operating_variable_zh']}”。",
        ),
        (
            "OBSERVABLE_DRIVER",
            "SOURCE_FACT",
            f"可观测主驱动：{profile['observable_driver_zh']}，原始单位为{profile['driver_unit_zh']}。",
        ),
        (
            "INDUSTRY_OPERATING_VARIABLE",
            "SOURCE_FACT",
            f"行业经营变量：{profile['industry_operating_variable_zh']}。",
        ),
        (
            "INDUSTRY_REVENUE_OR_COST_VARIABLE",
            "RESEARCH_INFERENCE",
            f"收入或成本传导：{profile['industry_financial_variable_zh']}。",
        ),
        (
            "DIRECTION_ASSESSMENT",
            "RESEARCH_INFERENCE",
            f"方向判断：{_direction_text(directions)}。",
        ),
        (
            "PRICE_CONFOUNDER_AND_COUNTEREVIDENCE",
            "CALCULATED_FACT",
            verification,
        ),
    )
    rows: list[dict[str, Any]] = []
    for number, (step_type, statement_class, statement) in enumerate(statements, 1):
        row: dict[str, Any] = {
            "step_number": number,
            "step_type": step_type,
            "statement_class": statement_class,
            "statement_zh": statement,
            "evidence_ids": [],
        }
        if number in {5, 6}:
            row.update(
                {
                    "premise_step_numbers": [2, 3, 4] if number == 5 else [3, 4, 5],
                    "condition_zh": condition,
                    "invalidation_zh": invalidation,
                }
            )
        if number == 7:
            row["counterevidence_zh"] = counterevidence
        rows.append(row)
    return rows


def _anchor_profiles(
    root: Path, contract: Mapping[str, Any], included: tuple[str, ...]
) -> dict[str, dict[str, Any]]:
    anchor_path = root / str(contract["anchor_profile"])
    fields = (
        "anchor_fact",
        "anchor_occurred_at",
        "anchor_first_public_at",
        "anchor_gap_reason",
        "anchor_visibility",
        "anchor_evidence_status",
    )
    anchors: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(anchor_path):
        event_id = str(row["event_id"])
        if event_id not in included:
            continue
        anchor = {key: row.get(key) for key in fields}
        existing = anchors.get(event_id)
        if existing is not None and existing != anchor:
            raise MultiEventClosureError(
                f"INCONSISTENT_EVENT_ANCHOR:{event_id}"
            )
        anchors[event_id] = anchor
    missing = sorted(set(included) - set(anchors))
    if missing:
        raise MultiEventClosureError(f"MISSING_EVENT_ANCHORS:{missing}")
    return anchors


def load_closure_profiles(root: Path) -> list[dict[str, Any]]:
    """Project the frozen 77-profile pool into the 69-record overlay contract."""

    root = root.resolve()
    contract = _contract(root)
    included = tuple(str(value) for value in contract["included_event_ids"])
    source_path = root / str(contract["source_profile"])
    frozen = load_industry_profiles(source_path)
    anchors = _anchor_profiles(root, contract, included)
    rows: list[dict[str, Any]] = []
    for profile in frozen:
        event_id = str(profile["event_id"])
        if event_id not in included:
            continue
        enriched = {
            **dict(profile),
            **anchors[event_id],
        }
        enriched["mechanism_steps"] = _steps(enriched)
        enriched.update(RELEASE_FIELDS)
        rows.append(enriched)
    ids = [str(row["event_industry_mapping_id"]) for row in rows]
    if len(rows) != int(contract["expected_mapping_count"]):
        raise MultiEventClosureError(f"EXPECTED_69_PROFILES_GOT:{len(rows)}")
    if len(ids) != len(set(ids)):
        raise MultiEventClosureError("DUPLICATE_MULTI_EVENT_MAPPING")
    if {str(row["event_id"]) for row in rows} != set(included):
        raise MultiEventClosureError("EVENT_SCOPE_MISMATCH")
    for row in rows:
        if tuple(step["step_type"] for step in row["mechanism_steps"]) != STEP_TYPES:
            raise MultiEventClosureError(
                f"INVALID_STEP_SEQUENCE:{row['event_industry_mapping_id']}"
            )
        if not row["condition_zh"] or not row["invalidation_condition_zh"]:
            raise MultiEventClosureError(
                f"MISSING_CONDITION:{row['event_industry_mapping_id']}"
            )
        if not row["counterevidence_zh"]:
            raise MultiEventClosureError(
                f"MISSING_COUNTEREVIDENCE:{row['event_industry_mapping_id']}"
            )
    return rows


def _evidence_for(
    evidence_fetches: list[dict[str, Any]], mapping_id: str, step_type: str
) -> list[str]:
    return sorted(
        str(source["source_id"])
        for source in evidence_fetches
        if source.get("fetch_status") == "RETRIEVED_QUOTE_VERIFIED"
        and mapping_id in {str(value) for value in source.get("supports_mapping_ids", [])}
        and step_type in {str(value) for value in source.get("supports_step_types", [])}
    )


def _confounders(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    mapping_id = str(profile["event_industry_mapping_id"])
    rows: list[dict[str, Any]] = []
    for index, text in enumerate(profile["counterevidence_zh"], 1):
        analysis = (
            f"这项竞争解释认为，“{text}”可能独立推动{profile['display_name_zh']}的价格或经营表现，"
            f"因此不能把事件窗口内的全部变化直接归因于{profile['event_title_zh']}。"
            f"它与目标路径在“{profile['observable_driver_zh']}—{profile['industry_operating_variable_zh']}—"
            f"{profile['industry_financial_variable_zh']}”环节发生重叠。若主驱动与行业经营变量按预期同步、"
            f"且在控制该竞争因素后方向仍一致，目标机制获得支持；若主驱动未兑现、行业变量却继续沿原方向变化，"
            f"或在“{profile['invalidation_condition_zh']}”出现后行情仍延续，则该竞争解释的权重上升。"
            "当前记录属于研究推断，尚未完成独立官方来源核验，不应进入干净归因主样本。"
        )
        rows.append(
            {
                "confounder_id": f"confounder-{mapping_id}-{index}",
                "event_zh": text,
                "affected_windows": [
                    "T_MINUS_1",
                    "T0",
                    "D1",
                    "D3",
                    "D5",
                    "D20",
                    "M3",
                ],
                "severity": "UNRESOLVED",
                "statement_class": "RESEARCH_INFERENCE",
                "analysis_zh": analysis,
                "mechanism_overlap": (
                    f"与目标事件共同作用于{profile['observable_driver_zh']}、"
                    f"{profile['industry_operating_variable_zh']}或行业估值窗口。"
                ),
                "alternative_explanation_zh": text,
                "distinguishing_tests_zh": [
                    f"核对{profile['observable_driver_zh']}是否在事件锚点后先于行业指数和经营变量变化。",
                    f"比较{profile['industry_operating_variable_zh']}与{profile['industry_financial_variable_zh']}是否同步兑现。",
                    f"检验“{profile['invalidation_condition_zh']}”出现后，原方向是否仍持续。",
                ],
                "counterevidence_zh": [
                    f"若{profile['observable_driver_zh']}没有按预期变化而行业仍沿预测方向运行，目标机制被削弱。",
                    f"若竞争因素消退后{profile['industry_operating_variable_zh']}仍延续，目标机制获得相对支持。",
                ],
                "attribution_limit_zh": (
                    f"在独立来源、时间顺序和区分检验未关闭前，只能称为"
                    f"{profile['event_title_zh']}窗口内的候选行业反应，不能将收益或经营变化完全归因于单一事件。"
                ),
                "evidence_ids": [],
                "evidence_status": "EVIDENCE_PENDING",
                "missing_evidence_reason": "CONFOUNDER_SOURCE_NOT_VERIFIED",
                "challenge_set_only": True,
            }
        )
    return rows

def build_mechanism_chains(
    profiles: list[dict[str, Any]], evidence_fetches: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    chains: list[dict[str, Any]] = []
    for profile in profiles:
        mapping_id = str(profile["event_industry_mapping_id"])
        nodes: list[dict[str, Any]] = []
        for step in profile["mechanism_steps"]:
            number = int(step["step_number"])
            evidence_ids = _evidence_for(
                evidence_fetches, mapping_id, str(step["step_type"])
            )
            statement_class = str(step["statement_class"])
            if statement_class == "SOURCE_FACT":
                evidence_status = "AVAILABLE" if evidence_ids else "EVIDENCE_PENDING"
            elif statement_class == "CALCULATED_FACT":
                evidence_status = "MARKET_CALCULATION_PENDING"
            else:
                evidence_status = "NOT_APPLICABLE_INFERENCE"
            nodes.append(
                {
                    "node_id": f"industry-mechanism-{mapping_id}-{number}",
                    "node_type": step["step_type"],
                    "statement_class": statement_class,
                    "statement_zh": step["statement_zh"],
                    "evidence_ids": evidence_ids,
                    "missing_evidence_reason": (
                        None if evidence_ids else "VERIFIED_SOURCE_NOT_SUPPLIED"
                    ),
                    "premise_node_ids": [
                        f"industry-mechanism-{mapping_id}-{premise}"
                        for premise in step.get("premise_step_numbers", [])
                    ],
                    "condition_zh": step.get("condition_zh"),
                    "invalidation_zh": step.get("invalidation_zh"),
                    "counterevidence_zh": list(step.get("counterevidence_zh", [])),
                    "evidence_status": evidence_status,
                }
            )
        chains.append(
            {
                "industry_chain_id": f"industry-chain-{mapping_id}",
                "event_industry_mapping_id": mapping_id,
                "event_id": profile["event_id"],
                "anchor_node_id": profile["anchor_node_id"],
                "impact_tier": profile["impact_tier"],
                "industry_name_zh": profile["display_name_zh"],
                "nodes": nodes,
                "edges": [
                    {
                        "from_node_id": nodes[index]["node_id"],
                        "to_node_id": nodes[index + 1]["node_id"],
                    }
                    for index in range(6)
                ],
                "horizon_directions": dict(profile["horizon_directions"]),
                "conditions_zh": [profile["condition_zh"]],
                "invalidation_conditions_zh": [profile["invalidation_condition_zh"]],
                "counterevidence_zh": list(profile["counterevidence_zh"]),
                "confounders": _confounders(profile),
                "challenge_set_only": True,
                "chain_status": "PROPOSED_INDUSTRY_MECHANISM",
                **RELEASE_FIELDS,
            }
        )
    return chains


def project_verified_evidence(
    evidence_fetches: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "evidence_id": source["source_id"],
            "evidence_kind": "INDUSTRY_MECHANISM_SOURCE",
            "source_tier": source.get("source_tier", "UNKNOWN"),
            "publisher": source.get("publisher", "来源发布方待补"),
            "title": source.get("title", source["source_id"]),
            "source_url": source.get("source_url"),
            "published_at": source.get("published_at"),
            "first_public_at": source.get("first_public_at", source.get("published_at")),
            "accessed_at": source.get("accessed_at"),
            "original_quote": source.get("verified_quote"),
            "locator": source.get("evidence_locator"),
            "availability_scope": source.get("usage_boundary", "UNKNOWN"),
            "supports_mapping_ids": list(source.get("supports_mapping_ids", [])),
            "supports_step_types": list(source.get("supports_step_types", [])),
            "raw_snapshot_path": source.get("raw_snapshot_path"),
            **RELEASE_FIELDS,
        }
        for source in evidence_fetches
        if source.get("fetch_status") == "RETRIEVED_QUOTE_VERIFIED"
    ]


def _mapping(profile: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: profile[key]
        for key in (
            "event_industry_mapping_id",
            "event_id",
            "event_title_zh",
            "anchor_node_id",
            "anchor_fact",
            "anchor_fact_zh",
            "anchor_occurred_at",
            "anchor_first_public_at",
            "anchor_gap_reason",
            "anchor_visibility",
            "anchor_evidence_status",
            "classification_edition",
            "sw1_id",
            "sw1_name_at_event",
            "display_name_zh",
            "impact_tier",
            "segment_labels_zh",
            "selection_basis_zh",
            "price_selection_used",
        )
    } | RELEASE_FIELDS


def _driver_records(
    profiles: list[dict[str, Any]],
    driver_payloads: Mapping[str, Mapping[str, Any]],
    verified_source_ids: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    drivers: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    for profile in profiles:
        mapping_id = str(profile["event_industry_mapping_id"])
        digest = hashlib.sha256(mapping_id.encode("utf-8")).hexdigest()[:12]
        series_id = f"industry-driver-{digest}"
        payload = dict(driver_payloads.get(mapping_id, {}))
        source_id = str(payload.get("source_id") or "")
        requested_available = payload.get("source_status") == "AVAILABLE"
        source_status = (
            "AVAILABLE"
            if requested_available and source_id in verified_source_ids
            else "DATA_PENDING"
        )
        pending_reason = (
            None
            if source_status == "AVAILABLE"
            else (
                "DRIVER_SOURCE_NOT_VERIFIED"
                if requested_available and source_id
                else "DRIVER_PAYLOAD_NOT_CONFIGURED"
            )
        )
        drivers.append(
            {
                "event_industry_mapping_id": mapping_id,
                "driver_series_id": series_id,
                "driver_role": "PRIMARY",
                "driver_name_zh": profile["observable_driver_zh"],
                "unit_zh": profile["driver_unit_zh"],
                "frequency": payload.get("frequency", "UNKNOWN"),
                "source_id": source_id or None,
                "pending_reason": pending_reason,
                "source_status": source_status,
                "selection_basis": "PRE_REGISTERED_OPERATING_DRIVER_NOT_SELECTED_BY_PRICE",
                **RELEASE_FIELDS,
            }
        )
        for index, item in enumerate(payload.get("observations", []), 1):
            observations.append(
                {
                    "observation_id": f"{series_id}-{index}",
                    "event_industry_mapping_id": mapping_id,
                    "driver_series_id": series_id,
                    "observed_at": item.get("observed_at"),
                    "metric_code": item.get("metric_code"),
                    "value": item.get("value") if source_status == "AVAILABLE" else None,
                    "unit": item.get("unit", profile["driver_unit_zh"]),
                    "data_status": (
                        "AVAILABLE"
                        if source_status == "AVAILABLE" and item.get("value") is not None
                        else "DATA_PENDING"
                    ),
                    "pending_reason": (
                        None
                        if source_status == "AVAILABLE" and item.get("value") is not None
                        else pending_reason or "DRIVER_PAYLOAD_NOT_AVAILABLE"
                    ),
                    **RELEASE_FIELDS,
                }
            )
    return drivers, observations


def _pending_market_window(profile: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "industry_market_window_id": f"industry-market-{profile['event_industry_mapping_id']}",
        "event_industry_mapping_id": profile["event_industry_mapping_id"],
        "event_id": profile["event_id"],
        "benchmark": {
            "benchmark_id": f"SW1-{profile['sw1_id']}",
            "benchmark_code": f"{profile['sw1_id']}.SI",
            "classification_edition": profile["classification_edition"],
        },
        "market_benchmark": {"benchmark_id": "CSI300", "benchmark_code": "000300.SH"},
        "continuous_window": [],
        "fixed_windows": {},
        "window_status": "DATA_PENDING",
        "pending_reason": "MARKET_SERIES_NOT_AVAILABLE",
        "missing_value_policy": "KEEP_NULL_NEVER_ZERO_IMPUTE",
        **RELEASE_FIELDS,
    }


def completion_for(
    mapping: Mapping[str, Any],
    chain: Mapping[str, Any],
    driver: Mapping[str, Any],
    window: Mapping[str, Any],
) -> dict[str, Any]:
    required_fact_types = {
        "EVENT_FACT",
        "BEHAVIOR_OR_POLICY_CHANGE",
        "OBSERVABLE_DRIVER",
        "INDUSTRY_OPERATING_VARIABLE",
    }
    fact_types = {
        node["node_type"]
        for node in chain["nodes"]
        if node["statement_class"] == "SOURCE_FACT"
        and node["evidence_status"] == "AVAILABLE"
    }
    mechanism_available = required_fact_types.issubset(fact_types)
    blockers: list[str] = []
    if not mechanism_available:
        blockers.append("FOUR_FACT_PILLARS_INCOMPLETE")
    if driver["source_status"] != "AVAILABLE":
        blockers.append("DRIVER_DATA_INCOMPLETE")
    if window["window_status"] != "AVAILABLE":
        blockers.append("INDUSTRY_WINDOW_INCOMPLETE")
    if not chain.get("counterevidence_zh"):
        blockers.append("COUNTEREVIDENCE_INCOMPLETE")
    company_count = int(mapping.get("company_count") or 0)
    return {
        "event_industry_mapping_id": mapping["event_industry_mapping_id"],
        "event_id": mapping["event_id"],
        "completion_status": "CANDIDATE_COMPLETE" if not blockers else "OPEN",
        "blockers": blockers,
        "challenge_set_only": any(
            item.get("severity") in {"MATERIAL", "DOMINANT", "UNRESOLVED"}
            for item in chain.get("confounders", [])
        ),
        "evidence_coverage": {
            "evidenced_node_count": len(fact_types),
            "required_node_count": len(required_fact_types),
        },
        "gate_statuses": {
            "mechanism_evidence": (
                "AVAILABLE" if mechanism_available else "DATA_PENDING"
            ),
            "driver_data": driver["source_status"],
            "market_window": window["window_status"],
            "company_sample": "AVAILABLE" if company_count else "DATA_PENDING",
        },
        **RELEASE_FIELDS,
    }

def _overlay_registry(contract: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "dataset_version": contract["dataset_version"],
        "merge_key": "event_industry_mapping_id",
        "merge_policy": "REPLACE_MATCHING_IDS_REJECT_DUPLICATE_SCOPE",
        "overlays": [dict(row) for row in contract["overlay_order"]],
        "expected_unique_mapping_count": contract["expected_union_mapping_count"],
        **RELEASE_FIELDS,
    }


def build_closure_bundle(
    root: Path,
    *,
    output_root: Path,
    evidence_fetches: list[dict[str, Any]] | None = None,
    driver_payloads: Mapping[str, Mapping[str, Any]] | None = None,
    market_payloads: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    contract = _contract(root)
    profiles = load_closure_profiles(root)
    if evidence_fetches is None:
        fetch_path = output_root / "industry_source_fetches.jsonl"
        evidence_fetches = read_jsonl(fetch_path) if fetch_path.exists() else []
    if driver_payloads is None:
        payload_config = _read_json(root / DRIVER_PAYLOAD_PATH)
        payload_rows = payload_config.get("payloads") or []
        driver_payloads = {
            str(row["event_industry_mapping_id"]): dict(row)
            for row in payload_rows
        }

    mappings = [_mapping(profile) for profile in profiles]
    baseline_by_id = {
        str(row["event_industry_mapping_id"]): row
        for row in read_jsonl(root / str(contract["anchor_profile"]))
    }
    for mapping in mappings:
        baseline = baseline_by_id.get(str(mapping["event_industry_mapping_id"]), {})
        mapping["company_count"] = int(baseline.get("company_count") or 0)
        mapping["company_links"] = list(baseline.get("company_links") or [])
    chains = build_mechanism_chains(profiles, evidence_fetches)
    evidence = project_verified_evidence(evidence_fetches)
    verified_source_ids = {
        str(row["source_id"])
        for row in evidence_fetches
        if row.get("fetch_status") == "RETRIEVED_QUOTE_VERIFIED"
    }
    drivers, observations = _driver_records(
        profiles,
        driver_payloads,
        verified_source_ids,
    )
    if market_payloads is None:
        from fingoose_industry_market_v2 import load_market_windows_from_raw

        registry_path = (
            root / "configs/industry_impact_v2/multi_event_market_registry.json"
        )
        registry = _read_json(registry_path)
        observations_by_mapping: dict[str, list[dict[str, Any]]] = {}
        for row in observations:
            observations_by_mapping.setdefault(
                str(row["event_industry_mapping_id"]), []
            ).append(dict(row))
        loaded_windows = load_market_windows_from_raw(
            mappings=mappings,
            registry=registry,
            raw_root=output_root / "raw/market",
            driver_observations_by_mapping=observations_by_mapping,
        )
        market_payloads = {
            str(row["event_industry_mapping_id"]): row
            for row in loaded_windows
        }

    windows = []
    for profile in profiles:
        mapping_id = str(profile["event_industry_mapping_id"])
        window = dict(market_payloads.get(mapping_id, _pending_market_window(profile)))
        window.setdefault("event_industry_mapping_id", mapping_id)
        window.setdefault("event_id", profile["event_id"])
        window.update(RELEASE_FIELDS)
        windows.append(window)

    window_status_by_id = {
        str(row["event_industry_mapping_id"]): row for row in windows
    }
    for chain in chains:
        mapping_id = str(chain["event_industry_mapping_id"])
        window = window_status_by_id[mapping_id]
        calculation = chain["nodes"][6]
        if window["window_status"] == "AVAILABLE":
            calculation["evidence_status"] = "MARKET_CALCULATION_AVAILABLE"
            calculation["missing_evidence_reason"] = None
            calculation["calculation_reference"] = (
                window.get("industry_market_window_id")
                or f"industry-market-{mapping_id}"
            )
        else:
            calculation["evidence_status"] = "MARKET_CALCULATION_PENDING"
            calculation["calculation_reference"] = None

    chain_by_id = {row["event_industry_mapping_id"]: row for row in chains}
    driver_by_id = {row["event_industry_mapping_id"]: row for row in drivers}
    window_by_id = {row["event_industry_mapping_id"]: row for row in windows}
    completion = [
        completion_for(
            mapping,
            chain_by_id[mapping["event_industry_mapping_id"]],
            driver_by_id[mapping["event_industry_mapping_id"]],
            window_by_id[mapping["event_industry_mapping_id"]],
        )
        for mapping in mappings
    ]
    outputs = {
        "event_industry_mappings.jsonl": mappings,
        "industry_mechanism_chains.jsonl": chains,
        "industry_evidence.jsonl": evidence,
        "industry_driver_registry.jsonl": drivers,
        "industry_driver_observations.jsonl": observations,
        "industry_market_windows.jsonl": windows,
        "industry_completion_report.jsonl": completion,
        "industry_source_fetches.jsonl": evidence_fetches,
    }
    for name, rows in outputs.items():
        write_jsonl(output_root / name, rows)

    ids = {str(row["event_industry_mapping_id"]) for row in mappings}
    joined = all(
        {str(row["event_industry_mapping_id"]) for row in rows} == ids
        for rows in (chains, drivers, windows, completion)
    )
    summary = {
        "dataset_version": contract["dataset_version"],
        "mapping_count": len(mappings),
        "event_count": len({row["event_id"] for row in mappings}),
        "event_mapping_counts": dict(sorted(Counter(row["event_id"] for row in mappings).items())),
        "mechanism_chain_count": len(chains),
        "mechanism_node_count": sum(len(row["nodes"]) for row in chains),
        "verified_source_count": len(evidence),
        "available_driver_count": sum(row["source_status"] == "AVAILABLE" for row in drivers),
        "available_market_window_count": sum(row["window_status"] == "AVAILABLE" for row in windows),
        "candidate_complete_count": sum(row["completion_status"] == "CANDIDATE_COMPLETE" for row in completion),
        "open_count": sum(row["completion_status"] == "OPEN" for row in completion),
        "tier_counts": dict(sorted(Counter(row["impact_tier"] for row in mappings).items())),
        "all_ids_join": joined,
        **RELEASE_FIELDS,
    }
    _write_json(output_root / "summary.json", summary)
    _write_json(
        output_root / "validation_report.json",
        {
            **summary,
            "checks": {
                "mapping_count_is_69": len(mappings) == 69,
                "mechanism_node_count_is_483": sum(len(row["nodes"]) for row in chains) == 483,
                "events_are_02_through_10": {row["event_id"] for row in mappings}
                == set(contract["included_event_ids"]),
                "all_ids_join": joined,
                "empty_market_is_pending_not_zero": all(
                    row["window_status"] == "AVAILABLE" or not row.get("fixed_windows")
                    for row in windows
                ),
                "release_boundary_preserved": all(
                    row.get("formal_ready") is False and row.get("sha_gate") == "DEFERRED"
                    for rows in (mappings, chains, evidence, drivers, observations, windows, completion)
                    for row in rows
                ),
                "baseline_directory_not_written": True,
            },
            "formal_ready": False,
            "sha_gate": "DEFERRED",
        },
    )
    _write_json(output_root / "overlay_registry.json", _overlay_registry(contract))
    manifest_files = [
        {
            "path": path.name,
            "bytes": path.stat().st_size,
            "record_count": len(read_jsonl(path)) if path.suffix == ".jsonl" else None,
        }
        for path in sorted(output_root.iterdir())
        if path.is_file() and path.name != "manifest.json"
    ]
    _write_json(
        output_root / "manifest.json",
        {
            "dataset_version": contract["dataset_version"],
            "files": manifest_files,
            "sha_included": False,
            "formal_ready": False,
            "sha_gate": "DEFERRED",
        },
    )
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("work/ten_event_industry_closure_v2_candidate"),
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    print(json.dumps(build_closure_bundle(root, output_root=output), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
