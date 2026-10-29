"""Build the independent FinGoose event-to-industry v2 candidate layer."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from fingoose_company_impact_io_v2 import read_jsonl, write_jsonl


DATASET_VERSION = "fingoose-industry-impact-high-quality-v2-candidate"
TIERS = {"CORE_DIRECT", "SECOND_ORDER", "CONDITIONAL"}
DIRECTIONS = {"POSITIVE", "NEGATIVE", "MIXED", "UNKNOWN"}
NODE_TYPES = (
    "EVENT_FACT",
    "BEHAVIOR_OR_POLICY_CHANGE",
    "OBSERVABLE_DRIVER",
    "INDUSTRY_OPERATING_VARIABLE",
    "INDUSTRY_REVENUE_OR_COST_VARIABLE",
    "DIRECTION_ASSESSMENT",
    "PRICE_CONFOUNDER_AND_COUNTEREVIDENCE",
)
WINDOW_KEYS = ("T_MINUS_1", "T0", "D1", "D3", "D5", "D20", "M3")


class IndustryImpactError(ValueError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _event_date(value: str) -> str:
    return value[:10]


def _direction_text(directions: Mapping[str, str]) -> str:
    labels = {"POSITIVE": "正向", "NEGATIVE": "负向", "MIXED": "混合", "UNKNOWN": "未知"}
    return "、".join(
        f"{name}{labels[directions[key]]}"
        for key, name in (("IMMEDIATE", "即时"), ("SHORT_TERM", "短期"), ("MEDIUM_TERM", "中期"))
    )


def load_industry_profiles(path: Path) -> list[dict[str, Any]]:
    config = _read_json(path)
    if config.get("dataset_version") != DATASET_VERSION:
        raise IndustryImpactError("DATASET_VERSION_MISMATCH")
    rows: list[dict[str, Any]] = []
    for event in config.get("events") or []:
        event_id = str(event["event_id"])
        edition = str(event["classification_edition"])
        for item in event.get("industries") or []:
            values = list(item.get("directions") or [])
            if len(values) != 3 or not set(values).issubset(DIRECTIONS):
                raise IndustryImpactError(f"INVALID_DIRECTIONS:{event_id}:{item.get('sw1_id')}")
            tier = str(item.get("tier") or "")
            if tier not in TIERS:
                raise IndustryImpactError(f"INVALID_TIER:{event_id}:{item.get('sw1_id')}")
            sw1_id = str(item["sw1_id"])
            mapping_id = f"event-industry-{event_id}-{sw1_id}"
            directions = dict(zip(("IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM"), values))
            display_name = str(item["name"])
            row = {
                "event_industry_mapping_id": mapping_id,
                "event_id": event_id,
                "event_title_zh": event["title_zh"],
                "anchor_fact_zh": event["anchor_fact_zh"],
                "anchor_node_id": event["anchor_node_id"],
                "anchor_id": f"anchor-{event['anchor_node_id']}",
                "classification_edition": edition,
                "sw1_id": sw1_id,
                "sw1_name_at_event": item.get("name_at_event", display_name),
                "display_name_zh": display_name,
                "impact_tier": tier,
                "segment_labels_zh": list(item["segments"]),
                "behavior_change_zh": event["behavior_change_zh"],
                "observable_driver_zh": item["driver"],
                "driver_unit_zh": item["unit"],
                "industry_operating_variable_zh": item["operating"],
                "industry_financial_variable_zh": item["financial"],
                "horizon_directions": directions,
                "condition_zh": item["condition"],
                "invalidation_condition_zh": item["invalidation"],
                "counterevidence_zh": list(event["counterevidence_zh"]),
                "selection_basis_zh": (
                    f"在读取事件后行业价格前，依据“{event['behavior_change_zh']}”是否通过"
                    f"“{item['driver']}”传至{display_name}的共同经营变量进行候选分层。"
                ),
                "price_selection_used": False,
                "review_status": "NEEDS_HUMAN_REVIEW",
                "formal_ready": False,
                "sha_gate": "DEFERRED",
            }
            rows.append(row)
    ids = [row["event_industry_mapping_id"] for row in rows]
    pairs = [(row["event_id"], row["sw1_id"]) for row in rows]
    if len(rows) != 77:
        raise IndustryImpactError(f"EXPECTED_77_PROFILES_GOT:{len(rows)}")
    if len(ids) != len(set(ids)) or len(pairs) != len(set(pairs)):
        raise IndustryImpactError("DUPLICATE_EVENT_INDUSTRY_MAPPING")
    return rows


def _source_catalog(root: Path) -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    primary = root / "data/market_event_attribution_v1/source_manifest.jsonl"
    if primary.exists():
        for row in read_jsonl(primary):
            catalog[str(row["source_id"])] = dict(row)
    candidate = root / "work/timeline_fast_candidate_v2/candidate_source_manifest.jsonl"
    if candidate.exists():
        for row in read_jsonl(candidate):
            source_id = str(row.get("candidate_source_id") or "")
            if source_id:
                catalog[source_id] = dict(row)
    audits = root / "work/timeline_fast_candidate_v2/candidate_source_audit.jsonl"
    if audits.exists():
        for row in read_jsonl(audits):
            source_id = f"supplemental-{row.get('attachment_node_id')}"
            if source_id in catalog:
                catalog[source_id] = {**catalog[source_id], **dict(row)}
    return catalog


def _company_links(root: Path) -> dict[tuple[str, str], list[dict[str, str]]]:
    path = root / "work/company_impact_high_quality_v2_candidate/event_company_map.jsonl"
    result: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    if not path.exists():
        return result
    for row in read_jsonl(path):
        classification = row.get("industry_classification") or {}
        key = (str(row["event_id"]), str(classification.get("sw1_id") or "UNKNOWN"))
        result[key].append({
            "mapping_id": str(row["mapping_id"]),
            "company_id": str(row["company_id"]),
            "company_code": str(row["company_code"]),
            "company_name": str(row["company_name"]),
        })
    return result


def _build_evidence(
    nodes: Mapping[str, Mapping[str, Any]],
    source_catalog: Mapping[str, Mapping[str, Any]],
    anchor_ids: Iterable[str],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for node_id in anchor_ids:
        node = nodes[node_id]
        for source_id in node.get("source_ids") or []:
            source_id = str(source_id)
            if source_id in seen:
                continue
            seen.add(source_id)
            source = dict(source_catalog.get(source_id) or {})
            locator = source.get("evidence_locator") or source.get("locator")
            output.append({
                "evidence_id": source_id,
                "evidence_kind": "EVENT_ANCHOR_SOURCE",
                "source_tier": source.get("source_tier") or source.get("tier") or "UNKNOWN",
                "publisher": source.get("publisher") or "来源发布方待补",
                "title": source.get("title") or source.get("publisher_label") or source_id,
                "source_url": source.get("source_url") or source.get("candidate_url"),
                "published_at": source.get("published_at") or node.get("first_public_at"),
                "evidence_summary": source.get("summary") or node.get("fact"),
                "original_quote": source.get("evidence_quote"),
                "locator": locator,
                "availability_scope": "PREDICTION_VISIBLE",
                "review_status": "SOURCE_VERIFIED" if source else "SOURCE_METADATA_PENDING",
                "formal_ready": False,
                "sha_gate": "DEFERRED",
            })
    return output


def _chain(profile: Mapping[str, Any], anchor: Mapping[str, Any]) -> dict[str, Any]:
    mapping_id = str(profile["event_industry_mapping_id"])
    event_evidence = list(anchor.get("source_ids") or [])
    directions = dict(profile["horizon_directions"])
    statements = (
        ("SOURCE_FACT", f"{profile['event_title_zh']}：{anchor['fact']}", event_evidence),
        ("RESEARCH_INFERENCE", str(profile["behavior_change_zh"]), []),
        ("RESEARCH_INFERENCE", str(profile["observable_driver_zh"]), []),
        ("RESEARCH_INFERENCE", str(profile["industry_operating_variable_zh"]), []),
        ("RESEARCH_INFERENCE", str(profile["industry_financial_variable_zh"]), []),
        ("RESEARCH_INFERENCE", _direction_text(directions), []),
        (
            "VERIFICATION_PROTOCOL",
            "核对申万行业指数相对沪深300表现、主驱动变量、重叠宏观事件与行业特有反证；价格不用于选择路径或生成方向。",
            [],
        ),
    )
    nodes = []
    for index, ((claim_kind, statement, evidence_ids), node_type) in enumerate(zip(statements, NODE_TYPES), 1):
        nodes.append({
            "node_id": f"industry-mechanism-{mapping_id}-{index}",
            "node_type": node_type,
            "claim_kind": claim_kind,
            "statement_zh": statement,
            "evidence_ids": evidence_ids,
        })
    return {
        "industry_chain_id": f"industry-chain-{mapping_id}",
        "event_industry_mapping_id": mapping_id,
        "event_id": profile["event_id"],
        "anchor_node_id": profile["anchor_node_id"],
        "impact_tier": profile["impact_tier"],
        "industry_name_zh": profile["display_name_zh"],
        "nodes": nodes,
        "edges": [
            {"from_node_id": nodes[index]["node_id"], "to_node_id": nodes[index + 1]["node_id"]}
            for index in range(6)
        ],
        "horizon_directions": directions,
        "conditions_zh": [profile["condition_zh"]],
        "invalidation_conditions_zh": [profile["invalidation_condition_zh"]],
        "counterevidence_zh": list(profile["counterevidence_zh"]),
        "chain_status": "PROPOSED_INDUSTRY_MECHANISM",
        "review_status": "NEEDS_HUMAN_REVIEW",
        "price_selection_used": False,
        "formal_ready": False,
        "sha_gate": "DEFERRED",
    }


def _driver(profile: Mapping[str, Any]) -> dict[str, Any]:
    mapping_id = str(profile["event_industry_mapping_id"])
    digest = hashlib.sha256(
        f"{profile['event_id']}|{profile['sw1_id']}|{profile['observable_driver_zh']}".encode("utf-8")
    ).hexdigest()[:12]
    return {
        "driver_registry_id": f"industry-driver-{digest}",
        "event_industry_mapping_id": mapping_id,
        "primary_driver": {
            "driver_series_id": f"driver-{digest}",
            "name_zh": profile["observable_driver_zh"],
            "unit_zh": profile["driver_unit_zh"],
            "frequency": "UNKNOWN",
            "timezone": "UNKNOWN",
            "calendar": "UNKNOWN",
            "source_status": "DATA_PENDING",
            "selection_basis_zh": "按事件后价格不可见原则，从行业机制链预先指定。",
        },
        "secondary_driver": None,
        "review_status": "NEEDS_HUMAN_REVIEW",
        "formal_ready": False,
        "sha_gate": "DEFERRED",
    }


def _market_window(
    profile: Mapping[str, Any],
    anchor: Mapping[str, Any],
    availability_audit: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "industry_market_window_id": f"industry-market-{profile['event_industry_mapping_id']}",
        "event_industry_mapping_id": profile["event_industry_mapping_id"],
        "event_id": profile["event_id"],
        "anchor_at": anchor.get("occurred_at"),
        "anchor_date": _event_date(str(anchor.get("occurred_at") or anchor.get("first_public_at") or "")),
        "benchmark": {
            "benchmark_id": f"SW1-{profile['sw1_id']}",
            "benchmark_code": f"{profile['sw1_id']}.SI",
            "classification_edition": profile["classification_edition"],
            "history_data_status": "DATA_PENDING",
        },
        "market_benchmark": {"benchmark_id": "CSI300", "benchmark_code": "000300.SH"},
        "continuous_window": {"start": "T-20", "end": "D20", "observations": []},
        "fixed_windows": {key: None for key in WINDOW_KEYS},
        "normalization": {"base": "COMMON_T_MINUS_1", "base_value": 100, "status": "DATA_PENDING"},
        "data_availability_gap": {
            "availability_audit_id": availability_audit["availability_audit_id"],
            "checked_at": availability_audit["checked_at"],
            "database": availability_audit["database"],
            "matched_tables": list(availability_audit.get("matched_tables") or []),
            "reason_codes": list(availability_audit["reason_codes"]),
            "gap_status": availability_audit["gap_status"],
            "execution_authenticity_status": availability_audit[
                "execution_authenticity_status"
            ],
            "licence_status": availability_audit["licence_status"],
        },
        "missing_value_policy": "KEEP_NULL_NEVER_ZERO_IMPUTE",
        "price_selection_used": False,
        "window_status": "DATA_PENDING",
        "review_status": "NEEDS_HUMAN_REVIEW",
        "formal_ready": False,
        "sha_gate": "DEFERRED",
    }


def build_industry_candidate_bundle(root: Path, *, output_root: Path) -> dict[str, Any]:
    root = root.resolve()
    output_root = output_root.resolve()
    profiles = load_industry_profiles(root / "configs/industry_impact_v2/event_industry_profiles.json")
    availability_audit = _read_json(
        root / "configs/industry_impact_v2/market_data_availability.json"
    )
    timeline = read_jsonl(root / "work/timeline_fast_candidate_v2/timeline_nodes.jsonl")
    timeline_by_id = {str(row["fast_node_id"]): row for row in timeline}
    missing = sorted({str(row["anchor_node_id"]) for row in profiles} - set(timeline_by_id))
    if missing:
        raise IndustryImpactError(f"MISSING_ANCHOR_NODES:{missing}")
    links = _company_links(root)
    mappings = []
    chains = []
    drivers = []
    windows = []
    completions = []
    for profile in profiles:
        anchor = timeline_by_id[str(profile["anchor_node_id"])]
        if anchor.get("evidence_status") != "VERIFIED_EXISTING":
            raise IndustryImpactError(f"ANCHOR_NOT_VERIFIED:{profile['anchor_node_id']}")
        company_links = links.get((str(profile["event_id"]), str(profile["sw1_id"])), [])
        mapping = {
            **profile,
            "anchor_fact": anchor.get("fact"),
            "anchor_occurred_at": anchor.get("occurred_at"),
            "anchor_first_public_at": anchor.get("first_public_at"),
            "anchor_evidence_status": anchor.get("evidence_status"),
            "anchor_gap_reason": anchor.get("gap_reason"),
            "anchor_visibility": anchor.get("visibility"),
            "event_evidence_ids": list(anchor.get("source_ids") or []),
            "company_links": company_links,
            "company_count": len(company_links),
        }
        mappings.append(mapping)
        chain = _chain(profile, anchor)
        driver = _driver(profile)
        window = _market_window(profile, anchor, availability_audit)
        chains.append(chain)
        drivers.append(driver)
        windows.append(window)
        missing_node_ids = [
            str(node["node_id"])
            for node in chain["nodes"]
            if not node.get("evidence_ids")
        ]
        evidence_coverage = {
            "required_node_count": len(chain["nodes"]),
            "evidenced_node_count": len(chain["nodes"]) - len(missing_node_ids),
            "missing_node_ids": missing_node_ids,
        }
        gate_statuses = {
            "mechanism_evidence": (
                "AVAILABLE" if not missing_node_ids else "DATA_PENDING"
            ),
            "driver_data": driver["primary_driver"]["source_status"],
            "market_window": window["window_status"],
            "company_sample": "AVAILABLE" if company_links else "DATA_PENDING",
        }
        blockers = []
        if missing_node_ids:
            blockers.append("MECHANISM_SUPPORT_EVIDENCE_INCOMPLETE")
        if gate_statuses["driver_data"] != "AVAILABLE":
            blockers.append("DRIVER_DATA_INCOMPLETE")
        if gate_statuses["market_window"] != "AVAILABLE":
            blockers.append("INDUSTRY_WINDOW_INCOMPLETE")
        if not company_links:
            blockers.append("COMPANY_SAMPLE_INCOMPLETE")
        if anchor.get("gap_reason"):
            blockers.append("ANCHOR_TIME_OR_SOURCE_GAP_PRESENT")
        if anchor.get("visibility") == "UNRESOLVED":
            blockers.append("ANCHOR_VISIBILITY_UNRESOLVED")
        completions.append({
            "event_industry_mapping_id": profile["event_industry_mapping_id"],
            "completion_status": "OPEN",
            "blockers": blockers,
            "challenge_set_only": False,
            "gate_statuses": gate_statuses,
            "evidence_coverage": evidence_coverage,
            "review_status": "NEEDS_HUMAN_REVIEW",
            "formal_ready": False,
            "sha_gate": "DEFERRED",
        })
    evidence = _build_evidence(
        timeline_by_id,
        _source_catalog(root),
        dict.fromkeys(str(row["anchor_node_id"]) for row in profiles),
    )
    output_root.mkdir(parents=True, exist_ok=True)
    files = {
        "event_industry_mappings.jsonl": mappings,
        "industry_mechanism_chains.jsonl": chains,
        "industry_evidence.jsonl": evidence,
        "industry_driver_registry.jsonl": drivers,
        "industry_market_windows.jsonl": windows,
        "industry_completion_report.jsonl": completions,
    }
    for name, rows in files.items():
        write_jsonl(output_root / name, rows)
    tier_counts = Counter(row["impact_tier"] for row in mappings)
    report = {
        "dataset_version": DATASET_VERSION,
        "mapping_count": len(mappings),
        "event_count": len({row["event_id"] for row in mappings}),
        "tier_counts": dict(sorted(tier_counts.items())),
        "mechanism_chain_count": len(chains),
        "mechanism_node_count": sum(len(row["nodes"]) for row in chains),
        "evidence_count": len(evidence),
        "driver_count": len(drivers),
        "market_window_count": len(windows),
        "candidate_complete_count": 0,
        "candidate_open_count": len(completions),
        "company_link_count": sum(row["company_count"] for row in mappings),
        "hard_failures": [],
        "formal_ready": False,
        "sha_gate": "DEFERRED",
    }
    _write_json(output_root / "summary.json", report)
    _write_json(output_root / "validation_report.json", {**report, "valid_candidate": True})
    manifest_files = sorted(path for path in output_root.iterdir() if path.is_file() and path.name != "manifest.json")
    _write_json(output_root / "manifest.json", {
        "dataset_version": DATASET_VERSION,
        "formal_ready": False,
        "sha_gate": "DEFERRED",
        "files": [
            {"path": path.name, "size": path.stat().st_size, "sha256": _sha256(path)}
            for path in manifest_files
        ],
    })
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("work/industry_impact_high_quality_v2_candidate"))
    args = parser.parse_args(argv)
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    print(json.dumps(build_industry_candidate_bundle(root, output_root=output), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
