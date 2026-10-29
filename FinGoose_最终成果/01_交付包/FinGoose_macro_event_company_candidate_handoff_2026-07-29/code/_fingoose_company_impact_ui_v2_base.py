"""Integrated Chinese UI projection for FinGoose company-impact v2."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

from fingoose_company_impact_io_v2 import read_jsonl


EVENT_TITLES = {
    "event-01": "WHO 将新冠疫情定性为全球大流行",
    "event-02": "俄乌冲突全面升级",
    "event-03": "美联储开启加息周期",
    "event-04": "中国防疫政策转向",
    "event-05": "硅谷银行倒闭与银行业冲击",
    "event-06": "OPEC+ 意外减产",
    "event-07": "红海航运危机升级",
    "event-08": "日本央行结束负利率",
    "event-09": "中国一揽子金融支持政策",
    "event-10": "美国对等关税政策公布",
}


def _by(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    return {str(row[field]): row for row in rows}


def _group(rows: list[dict[str, Any]], field: str) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        result[str(row.get(field))].append(row)
    return dict(result)


def _public_direction(row: Mapping[str, Any]) -> dict[str, Any]:
    allowed = (
        "direction_id", "mapping_id", "event_id", "company_id", "company_name",
        "industry", "horizons", "mechanism", "conditions", "invalidation_conditions",
        "confidence", "review_origin", "review_status", "binding_id",
        "candidate_binding_ids", "binding_selection_status", "claim_ids",
    )
    return {key: row.get(key) for key in allowed}


def _candidate_file(candidate: Path, fallback: Path, name: str) -> Path:
    preferred = candidate / name
    return preferred if preferred.exists() else fallback / name


def _merge_timeline_display_profiles(
    timeline: list[dict[str, Any]],
    profiles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for profile in profiles:
        node_id = str(profile.get("fast_node_id") or "")
        if not node_id:
            raise ValueError("timeline display profile missing fast_node_id")
        if node_id in by_id:
            raise ValueError(f"duplicate timeline display profile: {node_id}")
        by_id[node_id] = profile

    timeline_ids = {str(row.get("fast_node_id") or "") for row in timeline}
    profile_ids = set(by_id)
    missing = sorted(timeline_ids - profile_ids)
    extra = sorted(profile_ids - timeline_ids)
    if missing or extra:
        raise ValueError(
            f"timeline display profile coverage mismatch; missing={missing}, extra={extra}"
        )

    merged = []
    for row in timeline:
        node_id = str(row["fast_node_id"])
        profile = by_id[node_id]
        if profile.get("event_id") != row.get("event_id"):
            raise ValueError(f"timeline display event mismatch: {node_id}")
        title = str(profile.get("event_title_zh") or "").strip()
        summary = str(profile.get("event_summary_zh") or "").strip()
        if not title or not summary:
            raise ValueError(f"timeline display text missing: {node_id}")
        if not any("\u4e00" <= char <= "\u9fff" for char in title + summary):
            raise ValueError(f"timeline display text is not Chinese: {node_id}")
        item = dict(row)
        item["event_title_zh"] = title
        item["event_summary_zh"] = summary
        merged.append(item)
    return merged
def _load_transmission_registry(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, dict[str, Any]]]:
    result: dict[str, dict[str, dict[str, Any]]] = {
        "CHANNEL": {},
        "MARKET_SERIES": {},
    }
    required = {
        "CHANNEL": (
            "name_zh", "up_label_zh", "down_label_zh", "economic_meaning_zh",
        ),
        "MARKET_SERIES": (
            "code", "name_zh", "unit_zh", "economic_meaning_zh",
            "up_interpretation_zh", "down_interpretation_zh",
        ),
    }
    for row in rows:
        record_type = str(row.get("record_type") or "")
        registry_id = str(row.get("registry_id") or "")
        if record_type not in result:
            raise ValueError(f"unknown transmission registry type: {record_type}")
        if not registry_id:
            raise ValueError("transmission registry record missing registry_id")
        if registry_id in result[record_type]:
            raise ValueError(f"duplicate transmission registry record: {registry_id}")
        missing = [field for field in required[record_type] if not row.get(field)]
        if missing:
            raise ValueError(
                f"transmission registry fields missing for {registry_id}: {missing}"
            )
        chinese_text = "".join(str(row[field]) for field in required[record_type])
        if not any("\u4e00" <= char <= "\u9fff" for char in chinese_text):
            raise ValueError(f"transmission registry is not Chinese: {registry_id}")
        result[record_type][registry_id] = dict(row)
    return result


def _validate_transmission_registry_coverage(
    edges: list[dict[str, Any]],
    registry: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> None:
    channel_ids = {
        node_id.split("-channel-", 1)[1]
        for edge in edges
        for node_id in (str(edge.get("from_node_id")), str(edge.get("to_node_id")))
        if "-channel-" in node_id
    }
    series_ids = {
        node_id.split("-asset-", 1)[1]
        for edge in edges
        for node_id in (str(edge.get("from_node_id")), str(edge.get("to_node_id")))
        if "-asset-" in node_id
    }
    missing_channels = sorted(channel_ids - set(registry["CHANNEL"]))
    missing_series = sorted(series_ids - set(registry["MARKET_SERIES"]))
    if missing_channels or missing_series:
        raise ValueError(
            "transmission registry coverage mismatch; "
            f"channels={missing_channels}, series={missing_series}"
        )


def _ordered_unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _dedupe_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    seen = set()
    for row in rows:
        key = json.dumps(row, ensure_ascii=False, sort_keys=True)
        if key not in seen:
            seen.add(key)
            result.append(dict(row))
    return result


def _primary_direction(expected_path: Mapping[str, Any] | None) -> str:
    path = expected_path or {}
    for horizon in ("IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM"):
        value = str(path.get(horizon) or "")
        if value in {"UP", "DOWN"}:
            return value
    return "UNKNOWN"


def _project_operating_paths(
    companies: list[dict[str, Any]],
    timeline: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    timeline_by_id = _by(timeline, "fast_node_id")
    result = []
    for company in companies:
        source = company.get("mechanism_chain") or {}
        if not source:
            continue
        chain = dict(source)
        nodes = [dict(node) for node in source.get("nodes") or []]
        timeline_node = timeline_by_id.get(str(source.get("timeline_node_id")), {})
        if nodes and timeline_node:
            nodes[0]["statement"] = timeline_node.get("event_title_zh")
            nodes[0]["event_summary_zh"] = timeline_node.get("event_summary_zh")
        chain.update({
            "company_id": company.get("company_id"),
            "company_code": company.get("company_code"),
            "company_name": company.get("company_name"),
            "industry": company.get("industry"),
            "industry_classification": company.get("industry_classification"),
            "company_evidence": company.get("evidence") or [],
            "timeline": timeline_node,
            "nodes": nodes,
        })
        result.append(chain)
    return sorted(result, key=lambda row: str(row.get("company_code")))


def _build_macro_transmission_paths(
    edges: list[dict[str, Any]],
    timeline: list[dict[str, Any]],
    registry: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    logical_by_id: dict[str, dict[str, Any]] = {}
    for edge in edges:
        edge_id = str(edge["edge_id"])
        existing = logical_by_id.get(edge_id)
        if existing is None:
            logical = dict(edge)
            logical["_raw_bindings"] = [dict(edge)]
            logical_by_id[edge_id] = logical
            continue
        if (
            existing.get("event_id") != edge.get("event_id")
            or existing.get("from_node_id") != edge.get("from_node_id")
            or existing.get("to_node_id") != edge.get("to_node_id")
        ):
            raise ValueError(f"conflicting logical edge definition: {edge_id}")
        existing["_raw_bindings"].append(dict(edge))

    logical_edges = list(logical_by_id.values())
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    indegree: dict[str, int] = defaultdict(int)
    nodes = set()
    for edge in logical_edges:
        source = str(edge["from_node_id"])
        target = str(edge["to_node_id"])
        outgoing[source].append(edge)
        indegree[target] += 1
        nodes.update((source, target))
    for rows in outgoing.values():
        rows.sort(key=lambda row: (str(row.get("to_node_id")), str(row.get("edge_id"))))

    state: dict[str, int] = {}

    def visit(node_id: str) -> None:
        marker = state.get(node_id, 0)
        if marker == 1:
            raise ValueError(f"cycle in macro transmission graph at {node_id}")
        if marker == 2:
            return
        state[node_id] = 1
        for edge in outgoing.get(node_id, []):
            visit(str(edge["to_node_id"]))
        state[node_id] = 2

    for node_id in sorted(nodes):
        visit(node_id)

    roots = sorted(node_id for node_id in nodes if indegree[node_id] == 0)
    complete: list[list[dict[str, Any]]] = []

    def walk(node_id: str, chain: list[dict[str, Any]]) -> None:
        if "-asset-" in node_id:
            complete.append(chain)
            return
        for edge in outgoing.get(node_id, []):
            walk(str(edge["to_node_id"]), chain + [edge])

    for root in roots:
        walk(root, [])

    timeline_by_id = _by(timeline, "fast_node_id")
    used_binding_ids = set()
    result = []
    for index, chain in enumerate(complete, start=1):
        if not chain:
            continue
        node_ids = [str(chain[0]["from_node_id"])] + [
            str(edge["to_node_id"]) for edge in chain
        ]
        channel_node = next(
            (node_id for node_id in node_ids if "-channel-" in node_id), None
        )
        asset_node = next(
            (node_id for node_id in reversed(node_ids) if "-asset-" in node_id), None
        )
        if not channel_node or not asset_node:
            continue

        raw_edges = [
            raw
            for edge in chain
            for raw in edge.get("_raw_bindings") or [edge]
        ]
        channel_id = channel_node.split("-channel-", 1)[1]
        series_id = asset_node.split("-asset-", 1)[1]
        channel_record = dict(registry["CHANNEL"][channel_id])
        series_record = dict(registry["MARKET_SERIES"][series_id])
        channel_edge = next(
            edge for edge in chain if str(edge["to_node_id"]) == channel_node
        )
        asset_edge = next(
            edge for edge in reversed(chain) if str(edge["to_node_id"]) == asset_node
        )
        channel_direction = _primary_direction(channel_edge.get("expected_path"))
        asset_direction = _primary_direction(asset_edge.get("expected_path"))
        channel_record["direction"] = channel_direction
        channel_record["direction_label_zh"] = (
            channel_record.get("up_label_zh") if channel_direction == "UP"
            else channel_record.get("down_label_zh") if channel_direction == "DOWN"
            else channel_record.get("name_zh") + "\u65b9\u5411\u672a\u77e5"
        )
        series_record["expected_path"] = asset_edge.get("expected_path") or {}
        series_record["direction"] = asset_direction
        series_record["direction_interpretation_zh"] = (
            series_record.get("up_interpretation_zh") if asset_direction == "UP"
            else series_record.get("down_interpretation_zh") if asset_direction == "DOWN"
            else "\u5e02\u573a\u65b9\u5411\u672a\u77e5\uff0c\u4fdd\u6301\u62d2\u7b54"
        )

        anchor_ids = _ordered_unique([
            str(edge.get("anchor_fast_node_id") or "") for edge in raw_edges
        ])
        timeline_nodes = [
            timeline_by_id[anchor_id]
            for anchor_id in anchor_ids
            if anchor_id in timeline_by_id
        ]
        binding_ids = _ordered_unique([
            str(edge.get("binding_id") or "") for edge in raw_edges
        ])
        edge_ids = _ordered_unique([
            str(edge.get("edge_id") or "") for edge in raw_edges
        ])
        used_binding_ids.update(binding_ids)
        primary_timeline = timeline_nodes[0] if timeline_nodes else {}
        result.append({
            "macro_path_id": f"macro-path-{index:02d}-{channel_id}-{series_id}",
            "event_id": chain[0].get("event_id"),
            "anchor_fast_node_id": anchor_ids[0] if anchor_ids else "",
            "anchor_fast_node_ids": anchor_ids,
            "event_title_zh": (
                primary_timeline.get("event_title_zh")
                or "\u4e8b\u4ef6\u6807\u9898\u5f85\u8865"
            ),
            "event_summary_zh": primary_timeline.get("event_summary_zh") or "",
            "timeline_contexts": [
                {
                    "fast_node_id": node.get("fast_node_id"),
                    "event_title_zh": node.get("event_title_zh"),
                    "event_summary_zh": node.get("event_summary_zh"),
                    "occurred_at": node.get("occurred_at"),
                }
                for node in timeline_nodes
            ],
            "channel": channel_record,
            "market_indicator": series_record,
            "expected_path": asset_edge.get("expected_path") or {},
            "lag_ranges": [edge.get("lag") or {} for edge in raw_edges],
            "conditions": _ordered_unique([
                str(value)
                for edge in raw_edges
                for value in edge.get("conditions") or []
            ]),
            "invalidation_conditions": _ordered_unique([
                str(value)
                for edge in raw_edges
                for value in edge.get("invalidation_conditions") or []
            ]),
            "counterevidence": _ordered_unique([
                str(value)
                for edge in raw_edges
                for value in edge.get("counterevidence") or []
            ]),
            "event_fact_evidence": _dedupe_records([
                evidence
                for edge in raw_edges
                for evidence in edge.get("event_fact_evidence") or []
            ]),
            "mechanism_evidence": _dedupe_records([
                evidence
                for edge in raw_edges
                for evidence in edge.get("mechanism_evidence") or []
            ]),
            "confidence": min(float(edge.get("confidence") or 0) for edge in raw_edges),
            "binding_statuses": _ordered_unique([
                str(edge.get("binding_status") or "") for edge in raw_edges
            ]),
            "edge_support_statuses": _ordered_unique([
                str(edge.get("edge_support_status") or "") for edge in raw_edges
            ]),
            "binding_ids": binding_ids,
            "edge_ids": edge_ids,
            "node_ids": node_ids,
            "raw_edges": raw_edges,
        })

    unresolved = [
        {**dict(edge), "unresolved_reason": "NOT_IN_ROOT_TO_ASSET_PATH"}
        for edge in edges
        if str(edge.get("binding_id") or "") not in used_binding_ids
    ]
    result.sort(
        key=lambda row: (
            str(row["channel"].get("registry_id")),
            str(row["market_indicator"].get("registry_id")),
            str(row["macro_path_id"]),
        )
    )
    return result, unresolved

def build_ui_bundle(
    root: Path,
    *,
    candidate_root: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    upstream = root / "work/verifiable_evaluation_phase1_v2_candidate"
    fallback = root / "work/company_impact_high_quality_v2_candidate"
    candidate = (candidate_root or fallback).resolve()
    config = root / "configs/company_impact_high_quality_v2"

    def candidate_file(name: str) -> Path:
        return _candidate_file(candidate, fallback, name)

    transmission = read_jsonl(upstream / "dynamic_edge_bindings.jsonl")
    transmission_registry = _load_transmission_registry(
        read_jsonl(config / "transmission_node_display_registry.jsonl")
    )
    _validate_transmission_registry_coverage(transmission, transmission_registry)
    raw = {
        "timeline": _merge_timeline_display_profiles(
            read_jsonl(upstream / "timeline_nodes.jsonl"),
            read_jsonl(config / "timeline_display_profiles.jsonl"),
        ),
        "transmission": transmission,
        "transmission_registry": transmission_registry,
        "industry": read_jsonl(upstream / "event_industry_impacts.jsonl"),
        "mappings": read_jsonl(config / "event_company_map.jsonl"),
        "dossiers": read_jsonl(candidate_file("company_master_dossiers.jsonl")),
        "evidence": read_jsonl(candidate_file("company_evidence.jsonl")),
        "directions": read_jsonl(candidate_file("direction_assessments.jsonl")),
        "market": read_jsonl(candidate_file("company_market_windows.jsonl")),
        "relative": read_jsonl(candidate_file("relative_return_windows.jsonl")),
        "confounders": read_jsonl(candidate_file("company_confounders.jsonl")),
        "binding_reviews": read_jsonl(candidate_file("event_company_binding_reviews.jsonl")),
        "completion": read_jsonl(candidate_file("candidate_completion_report.jsonl")),
        "mechanism_chains": read_jsonl(candidate_file("event_company_mechanism_chains.jsonl")),
    }
    events = [project_event(raw, event_id) for event_id in sorted(EVENT_TITLES)]
    return {
        "dataset_version": "fingoose-company-impact-high-quality-v2-candidate",
        "formal_ready": False,
        "sha_gate": "DEFERRED",
        "events": events,
        "summary": {
            "event_count": len(events),
            "timeline_node_count": sum(len(event["timeline"]) for event in events),
            "transmission_path_count": sum(len(event["transmission_paths"]) for event in events),
            "company_evaluation_count": sum(len(event["companies"]) for event in events),
        },
    }


def project_event(bundle: Mapping[str, Any], event_id: str) -> dict[str, Any]:
    if "events" in bundle:
        for event in bundle["events"]:
            if event["event_id"] == event_id:
                return dict(event)
        raise KeyError(event_id)

    timeline = sorted(
        (dict(row) for row in bundle["timeline"] if row.get("event_id") == event_id),
        key=lambda row: (row.get("sequence", 999), str(row.get("occurred_at"))),
    )
    paths = []
    for row in bundle["transmission"]:
        if row.get("event_id") != event_id:
            continue
        paths.append({
            "edge_id": row.get("edge_id"),
            "binding_id": row.get("binding_id"),
            "anchor_fast_node_id": row.get("anchor_fast_node_id"),
            "from_node_id": row.get("from_node_id"),
            "to_node_id": row.get("to_node_id"),
            "expected_path": row.get("expected_path"),
            "lag": row.get("lag"),
            "confidence": row.get("confidence"),
            "binding_status": row.get("binding_status"),
            "edge_support_status": row.get("edge_support_status"),
            "conditions": row.get("conditions") or [],
            "invalidation_conditions": row.get("invalidation_conditions") or [],
            "mechanism_evidence_scope": row.get("mechanism_evidence_scope"),
            "review": row.get("review") or {},            "counterevidence": row.get("counterevidence") or [],
            "event_fact_evidence": row.get("event_fact_evidence") or [],
            "mechanism_evidence": row.get("mechanism_evidence") or [],
        })
    paths.sort(key=lambda row: str(row["binding_id"]))

    dossiers = _by(list(bundle["dossiers"]), "company_id")
    directions = _by(list(bundle["directions"]), "mapping_id")
    market = _by(list(bundle["market"]), "mapping_id")
    relative = _by(list(bundle["relative"]), "mapping_id")
    confounders = _by(list(bundle["confounders"]), "mapping_id")
    evidence = _group(list(bundle["evidence"]), "company_id")
    binding_reviews = _by(list(bundle["binding_reviews"]), "mapping_id")
    completion = _by(list(bundle["completion"]), "mapping_id")
    mechanism_chains = _by(list(bundle["mechanism_chains"]), "mapping_id")
    companies = []
    for mapping in bundle["mappings"]:
        if mapping.get("event_id") != event_id:
            continue
        mapping_id = str(mapping["mapping_id"])
        company_id = str(mapping["company_id"])
        companies.append({
            "mapping_id": mapping_id,
            "company_id": company_id,
            "company_code": mapping.get("company_code"),
            "company_name": mapping.get("company_name"),
            "industry": mapping.get("industry"),
            "industry_classification": mapping.get("industry_classification"),
            "lineage": {
                "event_id": mapping.get("event_id"),
                "anchor_id": mapping.get("anchor_id"),
                "binding_id": mapping.get("binding_id"),
                "candidate_binding_ids": mapping.get("candidate_binding_ids") or [],
                "industry_impact_id": mapping.get("industry_impact_id"),
                "company_id": company_id,
            },
            "dossier": dossiers.get(company_id),
            "evidence": evidence.get(company_id, []),
            "direction": _public_direction(directions.get(mapping_id, {})),
            "market_window": market.get(mapping_id),
            "relative_window": relative.get(mapping_id),
            "confounders": confounders.get(mapping_id),
            "binding_review": binding_reviews.get(mapping_id),
            "completion": completion.get(mapping_id),
            "mechanism_chain": mechanism_chains.get(mapping_id),
        })
    companies.sort(key=lambda row: str(row["company_code"]))

    industry_groups: dict[str, dict[str, Any]] = {}
    for company in companies:
        classification = company.get("industry_classification") or {}
        industry_id = str(classification.get("sw1_id") or "UNKNOWN")
        group = industry_groups.setdefault(industry_id, {
            "industry_id": industry_id,
            "industry_name": classification.get("sw1_name") or company.get("industry") or "待人工映射",
            "classification_status": classification.get("classification_status") or "NEEDS_HUMAN_REVIEW",
            "company_ids": [],
        })
        group["company_ids"].append(company["company_id"])

    operating_paths = _project_operating_paths(companies, timeline)
    macro_paths, unresolved_macro_edges = _build_macro_transmission_paths(
        paths,
        timeline,
        bundle["transmission_registry"],
    )
    return {
        "event_id": event_id,
        "title": EVENT_TITLES[event_id],
        "timeline": timeline,
        "transmission_paths": paths,
        "operating_transmission_paths": operating_paths,
        "macro_transmission_paths": macro_paths,
        "unresolved_macro_edges": unresolved_macro_edges,
        "industries": sorted(industry_groups.values(), key=lambda row: row["industry_id"]),
        "companies": companies,
        "summary": {
            "timeline_count": len(timeline),
            "verified_timeline_count": sum(row.get("evidence_status") == "VERIFIED_EXISTING" for row in timeline),
            "path_count": len(paths),
            "company_count": len(companies),
            "candidate_open_count": sum(
                row.get("completion", {}).get("completion_status") == "OPEN"
                for row in companies
            ),
        },
    }


STYLE = r"""
:root{--bg:#f4f5f2;--paper:#fff;--ink:#172124;--muted:#667175;--line:#d8ddda;--accent:#a63f35;--teal:#236b66;--gold:#9a721e;--soft:#eef2ef;--warn:#fff5dc;--sidebar:#172124}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--ink);font-family:"Microsoft YaHei","PingFang SC",Arial,sans-serif;font-size:14px;line-height:1.65;letter-spacing:0}.app{display:grid;grid-template-columns:280px minmax(0,1fr);min-height:100vh}.sidebar{position:sticky;top:0;height:100vh;background:var(--sidebar);color:#f5f7f5;padding:20px 14px;overflow:auto;z-index:20}.brand{padding:2px 8px 18px;border-bottom:1px solid #354144}.brand b{display:block;font:700 20px/1 Arial,sans-serif}.brand span{display:block;margin-top:8px;color:#aeb9b7;font-size:12px}.side-state{margin:14px 6px;padding:10px;border-left:3px solid #d4ad59;background:#202c2e;color:#cbd3d1;font-size:12px}.side-label{margin:18px 8px 8px;color:#849391;font-size:11px}.event-nav{display:grid;gap:5px}.event-button{width:100%;border:0;border-left:3px solid transparent;background:transparent;color:#d7dfdd;text-align:left;padding:10px 10px;cursor:pointer;font:inherit}.event-button:hover{background:#202d2f}.event-button.active{border-left-color:#d4ad59;background:#253335;color:#fff}.event-button small{display:block;color:#849391}.event-button span{display:block;font-weight:700}.event-button i{display:block;color:#aeb9b7;font-style:normal;font-size:11px}.side-foot{margin:20px 8px 0;padding-top:14px;border-top:1px solid #354144;color:#91a09d;font-size:11px}.workspace{min-width:0}.topbar{position:sticky;top:0;z-index:15;display:flex;align-items:center;justify-content:space-between;height:58px;padding:0 28px;background:rgba(255,255,255,.96);border-bottom:1px solid var(--line)}.topbar strong{font-size:14px}.topbar span{color:var(--muted);font-size:12px}.menu{display:none;border:1px solid var(--line);background:#fff;padding:7px 10px}.content{max-width:1440px;margin:0 auto;padding:30px 36px 70px}.hero{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:24px;align-items:end;padding:8px 0 24px;border-bottom:2px solid var(--ink)}.eyebrow{color:var(--accent);font-size:11px;font-weight:700}.hero h1{margin:6px 0 8px;font-size:30px;line-height:1.25}.hero p{margin:0;color:var(--muted);max-width:760px}.hero-status{text-align:right}.hero-status b{display:block;color:var(--accent)}.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:var(--line);margin:18px 0}.metric{background:var(--paper);padding:16px}.metric b{display:block;font-size:22px}.metric span{color:var(--muted);font-size:12px}.notice{padding:11px 14px;background:var(--warn);border-left:3px solid var(--gold);margin:0 0 12px;color:#5f4a1d}.section{padding:30px 0;border-top:1px solid var(--line)}.section-head{display:flex;justify-content:space-between;gap:20px;align-items:end;margin-bottom:16px}.section-head h2{margin:0;font-size:20px}.section-head p{margin:0;color:var(--muted);font-size:12px}.timeline{display:grid;gap:8px}.timeline-node{display:grid;grid-template-columns:150px 18px minmax(0,1fr);gap:12px;align-items:stretch;border:1px solid var(--line);background:var(--paper);padding:0;cursor:pointer;text-align:left;color:inherit}.timeline-node:hover,.timeline-node.selected{border-color:var(--teal);box-shadow:inset 3px 0 var(--teal)}.timeline-time{padding:14px;color:var(--muted);font-size:12px}.timeline-rail{position:relative}.timeline-rail:before{content:"";position:absolute;left:8px;top:0;bottom:0;width:1px;background:var(--line)}.timeline-rail:after{content:"";position:absolute;left:4px;top:19px;width:9px;height:9px;border-radius:50%;background:var(--accent)}.timeline-body{padding:12px 14px 12px 0}.timeline-body h3{margin:0 0 4px;font-size:14px}.timeline-body p{margin:0;color:#3e494c}.chips{display:flex;flex-wrap:wrap;gap:5px;margin-top:7px}.chip{display:inline-flex;align-items:center;min-height:24px;padding:2px 7px;border:1px solid var(--line);background:var(--soft);font-size:11px}.chip.good{color:var(--teal)}.chip.warn{color:#855f13;background:var(--warn)}.evidence-link{color:var(--teal);text-decoration:none}.evidence-link:hover{text-decoration:underline}.graph-toolbar{display:flex;gap:8px;margin-bottom:10px}.plain-button{border:1px solid var(--line);background:#fff;padding:7px 10px;cursor:pointer}.path-list{display:grid;gap:7px}.path-row{display:grid;grid-template-columns:minmax(150px,1fr) 32px minmax(150px,1fr) auto;gap:10px;align-items:center;padding:12px 14px;background:var(--paper);border:1px solid var(--line)}.path-row.selected{border-color:var(--accent)}.path-node b{display:block}.path-node small{color:var(--muted)}.arrow{color:var(--accent);font-size:20px;text-align:center}.path-meta{text-align:right;font-size:11px;color:var(--muted)}.industry-strip{display:flex;flex-wrap:wrap;gap:8px}.industry-button{border:1px solid var(--line);background:#fff;padding:10px 12px;text-align:left;cursor:pointer}.industry-button.active{border-color:var(--teal);background:#eaf4f2}.company-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.company-button{border:1px solid var(--line);background:var(--paper);padding:14px;text-align:left;cursor:pointer;min-height:150px}.company-button:hover,.company-button.active{border-color:var(--accent);box-shadow:inset 0 -3px var(--accent)}.company-button h3{margin:0;font-size:16px}.company-button p{margin:8px 0;color:var(--muted)}.directions{display:grid;grid-template-columns:repeat(3,1fr);gap:5px}.direction{padding:5px;background:var(--soft);font-size:11px;text-align:center}.direction.positive{color:#176454}.direction.negative{color:#9b3028}.detail{margin-top:18px;background:var(--paper);border-top:3px solid var(--ink);padding:20px}.detail-head{display:flex;justify-content:space-between;gap:14px}.detail h3{margin:0;font-size:20px}.detail h4{margin:22px 0 8px;font-size:14px}.detail-grid{display:grid;grid-template-columns:1.25fr .75fr;gap:24px}.chart-wrap{aspect-ratio:760/250;border:1px solid var(--line);background:#fff;min-height:220px}.chart-wrap svg{display:block;width:100%;height:100%}.legend{display:flex;gap:16px;color:var(--muted);font-size:11px}.legend i{display:inline-block;width:16px;height:3px;margin-right:5px;vertical-align:middle}.table-wrap{overflow:auto}.market-table{width:100%;border-collapse:collapse;min-width:720px}.market-table th,.market-table td{padding:8px;border-bottom:1px solid var(--line);text-align:right;font-size:12px}.market-table th:first-child,.market-table td:first-child{text-align:left}.evidence-list,.confounder-list{display:grid;gap:7px}.evidence-item,.confounder-item{padding:10px 0;border-bottom:1px solid var(--line)}.evidence-item p,.confounder-item p{margin:4px 0;color:#465154}.empty{padding:15px;border:1px dashed var(--line);color:var(--muted)}.footer{padding:24px 0;border-top:1px solid var(--line);color:var(--muted);font-size:11px}@media(max-width:1050px){.app{grid-template-columns:240px minmax(0,1fr)}.content{padding:24px}.company-grid{grid-template-columns:1fr}.detail-grid{grid-template-columns:1fr}}@media(max-width:760px){.app{display:block}.sidebar{position:fixed;left:0;top:0;bottom:0;width:280px;transform:translateX(-100%);transition:.2s;box-shadow:10px 0 25px rgba(0,0,0,.25)}.sidebar.open{transform:translateX(0)}.menu{display:block}.topbar{height:52px;padding:0 12px}.topbar span{display:none}.content{padding:18px 12px 50px}.hero{grid-template-columns:1fr}.hero h1{font-size:23px}.hero-status{text-align:left}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.timeline-node{grid-template-columns:105px 14px minmax(0,1fr)}.path-row{grid-template-columns:1fr 24px 1fr}.path-meta{grid-column:1/-1;text-align:left}.detail{padding:14px}.section-head{display:block}.section-head p{margin-top:4px}}
/* Keep intrinsic SVG and long dossier content inside the responsive detail grid. */
.detail-grid>*{min-width:0}@media(max-width:1050px){.detail-grid{grid-template-columns:minmax(0,1fr)}}
@media(max-width:760px){.chart-wrap{min-height:0;aspect-ratio:760/250}.detail-head{display:block}.detail-head>.chip{margin-top:8px}}
.mechanism-summary{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;margin:8px 0 12px}.mechanism-summary p{margin:0;color:var(--muted)}
.mechanism-flow{border-top:1px solid var(--line);border-bottom:1px solid var(--line);background:#fbfcfa}
.mechanism-step{display:grid;grid-template-columns:44px minmax(0,1fr)}
.mechanism-index{position:relative;display:flex;align-items:flex-start;justify-content:center;padding-top:15px;color:#fff;font-weight:700;font-size:11px}
.mechanism-index:before{content:"";position:absolute;top:0;bottom:0;left:21px;width:2px;background:#c7d4cf}
.mechanism-index span{position:relative;z-index:1;display:grid;place-items:center;width:25px;height:25px;border-radius:50%;background:var(--teal)}
.mechanism-copy{min-width:0;padding:12px 14px 13px 4px;border-bottom:1px solid var(--line)}.mechanism-step:last-child .mechanism-copy{border-bottom:0}
.mechanism-copy b{display:block;font-size:13px}.mechanism-copy p{margin:3px 0 0;color:#394548}.mechanism-copy small{color:var(--muted)}
.mechanism-meta{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:10px 0}.mechanism-meta>div{padding:9px 10px;border-left:3px solid var(--teal);background:var(--soft)}
.closure-wrap{overflow:auto}.closure-table{width:100%;min-width:820px;border-collapse:collapse}.closure-table th,.closure-table td{padding:8px 9px;border-bottom:1px solid var(--line);text-align:left;font-size:12px}.gate-ready{color:var(--teal);font-weight:700}.gate-open{color:#956116;font-weight:700}
.tech-details{margin:12px 0;border:1px solid var(--line);background:#fafbfa}.tech-details summary{cursor:pointer;padding:10px 12px;font-weight:700}.tech-body{padding:0 12px 12px;color:#465154}.tech-body code{overflow-wrap:anywhere}
@media(max-width:760px){.mechanism-summary{display:block}.mechanism-meta{grid-template-columns:1fr}.mechanism-copy{padding-right:8px}.mechanism-index{grid-column:1}.closure-table{min-width:720px}}
.timeline-node:focus-visible{outline:2px solid var(--teal);outline-offset:2px}
.timeline-body{min-width:0}.timeline-body h3{margin:0 0 6px;font-size:16px;line-height:1.45;overflow-wrap:anywhere}
.timeline-meta{display:flex;flex-wrap:wrap;gap:5px 12px;margin:0 0 7px;color:var(--muted);font-size:11px}
.timeline-summary{margin:0;color:#3e494c;overflow-wrap:anywhere}
.timeline-tech{margin-top:9px;border-top:1px solid var(--line);font-size:11px;color:var(--muted)}
.timeline-tech summary{width:max-content;max-width:100%;padding:7px 0 2px;cursor:pointer;color:var(--teal);font-weight:700}
.timeline-tech-body{padding:5px 0 2px}.timeline-tech dl{display:grid;grid-template-columns:92px minmax(0,1fr);gap:4px 10px;margin:0}
.timeline-tech dt{font-weight:700;color:#526064}.timeline-tech dd{min-width:0;margin:0;overflow-wrap:anywhere;color:#657174}
@media(max-width:760px){.timeline-node{grid-template-columns:92px 12px minmax(0,1fr)}.timeline-time{padding:12px 6px 12px 10px;overflow-wrap:anywhere}.timeline-body{padding-right:10px}.timeline-tech dl{grid-template-columns:1fr;gap:1px}.timeline-tech dd{margin-bottom:5px}}
.transmission-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px}
.transmission-tabs{display:inline-grid;grid-template-columns:repeat(2,minmax(120px,1fr));padding:3px;border:1px solid var(--line);background:#e8ece9}
.transmission-tab{min-height:36px;border:0;background:transparent;color:#536064;padding:7px 14px;cursor:pointer;font:inherit;font-weight:700}
.transmission-tab.active{background:var(--paper);color:var(--ink);box-shadow:0 1px 4px rgba(23,33,36,.12)}
.transmission-stack{display:grid;gap:14px}
.transmission-card{min-width:0;background:var(--paper);border:1px solid var(--line);border-left:4px solid var(--teal)}
.transmission-card.macro{border-left-color:var(--accent)}
.transmission-card-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;padding:14px 16px;border-bottom:1px solid var(--line)}
.transmission-card-head h3{margin:2px 0 3px;font-size:17px}.transmission-card-head p{margin:0;color:var(--muted)}
.transmission-flow-wrap{overflow-x:auto}.transmission-flow{display:grid;grid-template-columns:repeat(7,minmax(150px,1fr));min-width:1050px}
.transmission-flow.macro-flow{grid-template-columns:minmax(250px,1.2fr) 34px minmax(220px,1fr) 34px minmax(270px,1.2fr);min-width:880px;align-items:stretch}
.transmission-step{min-width:0;padding:14px 13px;border-right:1px solid var(--line);background:#fbfcfa}
.transmission-step:last-child{border-right:0}.transmission-step small{display:block;color:var(--muted);font-size:10px;font-weight:700}.transmission-step b{display:block;margin:4px 0;font-size:13px}.transmission-step p{margin:0;color:#455154;font-size:12px;overflow-wrap:anywhere}
.transmission-arrow{display:grid;place-items:center;color:var(--accent);font-size:22px;background:#f4f6f4}
.transmission-card-meta{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;background:var(--line);border-top:1px solid var(--line)}
.transmission-card-meta>div{min-width:0;padding:11px 13px;background:var(--paper);font-size:12px}.transmission-card-meta b{display:block;margin-bottom:3px}
.transmission-evidence{padding:12px 16px;border-top:1px solid var(--line);background:#fbfcfa}.transmission-evidence p{margin:4px 0;color:#465154}
.transmission-actions{display:flex;flex-wrap:wrap;gap:7px;align-items:center}.link-button{border:0;background:transparent;color:var(--teal);padding:3px 0;cursor:pointer;font:inherit;font-weight:700}
.macro-indicator-code{display:inline-flex;margin:5px 0;padding:2px 6px;background:#edf1ef;color:#354144;font:700 11px/1.6 Consolas,monospace}
.macro-directions{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px}
.raw-details{margin:0;border-top:1px solid var(--line);background:#fafbfa}.raw-details summary{cursor:pointer;padding:10px 16px;color:var(--teal);font-weight:700}.raw-details-body{padding:0 16px 14px;color:#526064;font-size:11px}.raw-details-body code{overflow-wrap:anywhere}
.filter-note{margin-bottom:10px;padding:9px 12px;border-left:3px solid var(--gold);background:var(--warn);color:#684f1c}
@media(max-width:760px){.transmission-toolbar{display:block}.transmission-tabs{display:grid;width:100%}.transmission-toolbar>.plain-button{margin-top:8px}.transmission-card-head{display:block}.transmission-actions{margin-top:8px}.transmission-card-meta{grid-template-columns:1fr}.transmission-flow{grid-template-columns:1fr;min-width:0}.transmission-flow.macro-flow{grid-template-columns:1fr;min-width:0}.transmission-step{border-right:0;border-bottom:1px solid var(--line)}.transmission-arrow{min-height:30px;transform:rotate(90deg)}}

"""


SCRIPT = r"""
const DATA=window.FINGOOSE_COMPANY_IMPACT_V2;
const state={eventId:DATA.events[0].event_id,nodeId:null,companyId:null,industryId:null,transmissionMode:'operating'};
const zhStatus={VERIFIED_EXISTING:'已有证据',PENDING_EVIDENCE:'待补证',NEEDS_HUMAN_REVIEW:'待人工审核',PARTIALLY_VERIFIED:'部分验证',DATA_PENDING:'数据待补',UNVERIFIED:'未核实',CANDIDATES_REGISTERED_NEEDS_BODY_REVIEW:'候选已登记，正文待审',SEARCH_PENDING:'检索待完成',AVAILABLE:'可用',CHALLENGE_ONLY:'仅挑战集',OFFICIAL_HISTORY_ASOF_MATCHED:'官方历史分类已按事件日匹配',VERIFIED_ACTIVE_ASOF:'事件日有效',SOURCE_VERIFIED_RULE_APPLIED:'来源已核验，规则已应用'};
const zhPhase={PRECONDITION:'前置背景',INITIAL_SHOCK:'首次冲击',ESCALATION:'升级',POLICY_RESPONSE:'政策响应',EASING:'缓和',SECONDARY_SHOCK:'二次冲击'};
const zhDirection={POSITIVE:'正向',NEGATIVE:'负向',MIXED:'混合',NEUTRAL:'中性',UNKNOWN:'未知',UP:'上行',DOWN:'下行'};
const horizons=[['T_MINUS_1','T-1'],['T0','T0'],['D1','D1'],['D3','D3'],['D5','D5'],['D20','D20']];
const esc=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const fmt=value=>value==null?'数据待补':Number(value).toLocaleString('zh-CN',{maximumFractionDigits:4});
const pct=value=>value==null?'数据待补':(Number(value)*100).toFixed(2)+'%';
const status=value=>zhStatus[value]||value||'数据待补';
const direction=value=>zhDirection[value]||value||'未知';
function humanNode(id){const text=String(id||'');const token=text.split('-').slice(3).join('-')||text;const map={'shock':'事件冲击','risk-appetite':'风险偏好渠道','safe-haven-demand':'避险需求渠道','energy-supply':'能源供应渠道','discount-rate':'贴现率渠道','rate-expectations':'利率预期渠道','rate-differential':'利差渠道','dollar-liquidity':'美元流动性渠道','global-demand':'全球需求渠道','bank-funding':'银行融资渠道'};for(const [key,label] of Object.entries(map)){if(token.includes(key))return label}if(text.includes('-asset-'))return '资产：'+token.toUpperCase();if(text.includes('-intermediate-'))return '中间变量：'+token.toUpperCase();return token||'待命名节点'}
function currentEvent(){return DATA.events.find(event=>event.event_id===state.eventId)}
function renderSidebar(){document.getElementById('event-nav').innerHTML=DATA.events.map(event=>`<button class="event-button ${event.event_id===state.eventId?'active':''}" data-event="${event.event_id}"><small>${event.event_id.toUpperCase()}</small><span>${esc(event.title)}</span><i>${event.summary.verified_timeline_count}/${event.summary.timeline_count} 节点有证据 · ${event.summary.company_count} 家公司</i></button>`).join('');document.querySelectorAll('[data-event]').forEach(button=>button.onclick=()=>{state.eventId=button.dataset.event;state.nodeId=null;state.industryId=null;state.companyId=null;render();document.getElementById('sidebar').classList.remove('open')})}
function eventEvidence(node){const evidence=(node.evidence||[])[0];if(!evidence)return '<span class="chip warn">无可展示证据</span>';return `<a class="evidence-link" href="${esc(evidence.url)}" target="_blank" rel="noopener noreferrer">证据：${esc(evidence.publisher||evidence.source_id)}</a>`}
function renderTimeline(event){return event.timeline.map(node=>`<article class="timeline-node ${state.nodeId===node.fast_node_id?'selected':''}" data-node="${esc(node.fast_node_id)}" role="button" tabindex="0" aria-label="${esc(node.event_title_zh)}"><span class="timeline-time">${esc(node.occurred_at||'\u65f6\u95f4\u5f85\u8865')}</span><span class="timeline-rail"></span><div class="timeline-body"><h3>${esc(node.event_title_zh)}</h3><div class="timeline-meta"><span>${esc(zhPhase[node.phase]||node.phase||'\u9636\u6bb5\u5f85\u5b9a')}</span><span>\u53d1\u751f\u65f6\u95f4 ${esc(node.occurred_at||'\u5f85\u8865')}</span><span>\u65f6\u95f4\u7cbe\u5ea6 ${esc(node.occurred_at_precision||node.first_public_at_precision||'\u5f85\u8865')}</span></div><p class="timeline-summary">${esc(node.event_summary_zh)}</p><div class="chips"><span class="chip ${node.evidence_status==='VERIFIED_EXISTING'?'good':'warn'}">${esc(status(node.evidence_status))}</span><span class="chip">${esc(node.node_action||'\u52a8\u4f5c\u5f85\u5b9a')}</span>${eventEvidence(node)}</div><details class="timeline-tech"><summary>\u6280\u672f\u8be6\u60c5</summary><div class="timeline-tech-body"><dl><dt>\u8282\u70b9 ID</dt><dd>${esc(node.fast_node_id)}</dd><dt>\u539f\u59cb\u4e8b\u5b9e</dt><dd>${esc(node.fact||'\u5f85\u8865')}</dd><dt>\u6765\u6e90 ID</dt><dd>${esc((node.source_ids||[]).join('\u3001')||'\u5f85\u8865')}</dd><dt>\u9996\u6b21\u516c\u5f00</dt><dd>${esc(node.first_public_at||'\u5f85\u8865')}</dd></dl></div></details></div></article>`).join('')}

function pathAnchors(path,mode){return mode==='operating'?[path.timeline_node_id]:(path.anchor_fast_node_ids||[path.anchor_fast_node_id])}
function filterPathSet(paths,mode){if(!state.nodeId)return {paths,note:''};const matched=paths.filter(path=>pathAnchors(path,mode).includes(state.nodeId));if(matched.length)return {paths:matched,note:''};return {paths,note:'\u5f53\u524d\u65f6\u95f4\u8282\u70b9\u6ca1\u6709\u76f4\u63a5\u7ed1\u5b9a\u7684\u5b8c\u6574\u8def\u5f84\uff0c\u4ee5\u4e0b\u7ee7\u7eed\u663e\u793a\u8be5\u4e8b\u4ef6\u5168\u90e8\u8def\u5f84\u3002'}}

function renderOperatingPaths(event){
  const filtered=filterPathSet(event.operating_transmission_paths||[],'operating');
  if(!filtered.paths.length)return '<div class="empty">\u7ecf\u8425\u5f71\u54cd\u94fe\u5f85\u751f\u6210\u3002</div>';
  const cards=filtered.paths.map(path=>{
    const company=event.companies.find(item=>item.mapping_id===path.mapping_id||item.company_id===path.company_id)||{};
    const flow=(path.nodes||[]).map((node,index)=>`<div class="transmission-step"><small>${index+1} / 7 &middot; ${esc(mechanismLabels[node.node_type]||node.node_type)}</small><b>${esc(node.statement)}</b>${chainEvidenceHtml(node,company,event)}</div>`).join('');
    const h=path.horizon_directions||{};
    const metrics=(path.operating_metrics||[]).map(item=>`<span class="chip">${esc(item.name)} &middot; ${esc(item.unit)}</span>`).join('');
    const edgeIds=(path.edges||[]).map(item=>item.edge_id).join('\u3001');
    const nodeIds=(path.nodes||[]).map(item=>item.node_id).join('\u3001');
    return `<article class="transmission-card operating"><header class="transmission-card-head"><div><span class="eyebrow">${esc(path.timeline?.event_title_zh||'\u4e8b\u4ef6\u951a\u70b9\u5f85\u8865')}</span><h3>${esc(path.company_name)} &middot; ${esc(path.industry||'\u884c\u4e1a\u5f85\u6620\u5c04')}</h3><p>${esc(path.timeline?.event_summary_zh||'')}</p></div><div class="transmission-actions"><span class="chip warn">${esc(status(path.review_status))}</span><button class="link-button" data-path-company="${esc(path.company_id)}">\u67e5\u770b\u516c\u53f8\u4ef7\u683c\u4e0e\u8bc1\u636e</button></div></header><div class="transmission-flow-wrap"><div class="transmission-flow">${flow}</div></div><div class="transmission-card-meta"><div><b>\u5373\u65f6 / \u77ed\u671f / \u4e2d\u671f</b>${esc(direction(h.IMMEDIATE))} / ${esc(direction(h.SHORT_TERM))} / ${esc(direction(h.MEDIUM_TERM))}</div><div><b>\u53ef\u89c2\u6d4b\u7ecf\u8425\u6307\u6807</b>${metrics||'\u6307\u6807\u5f85\u8865'}</div><div><b>\u751f\u6548\u4e0e\u5931\u6548\u8fb9\u754c</b>${esc((path.conditions||[]).join('\uff1b')||'\u5f85\u8865')}<br><span class="chip warn">${esc((path.invalidation_conditions||[]).join('\uff1b')||'\u5f85\u8865')}</span></div></div><details class="raw-details"><summary>\u5e95\u5c42\u7ed1\u5b9a\u4e0e\u6280\u672f\u8be6\u60c5</summary><div class="raw-details-body"><p><b>mapping_id:</b> <code>${esc(path.mapping_id)}</code></p><p><b>primary_binding_id:</b> <code>${esc(path.primary_binding_id)}</code></p><p><b>chain_id:</b> <code>${esc(path.chain_id)}</code></p><p><b>node_ids:</b> <code>${esc(nodeIds)}</code></p><p><b>edge_ids:</b> <code>${esc(edgeIds)}</code></p><p><b>\u53d1\u5e03\u8fb9\u754c:</b> formal_ready=false &middot; SHA DEFERRED &middot; ${esc(path.chain_status)}</p></div></details></article>`;
  }).join('');
  return `${filtered.note?`<div class="filter-note">${esc(filtered.note)}</div>`:''}<div class="transmission-stack">${cards}</div>`;
}

function macroEvidenceHtml(records,label){
  if(!records?.length)return `<span class="chip warn">${esc(label)}\u5f85\u8865</span>`;
  return records.map(item=>`<div class="evidence-item"><b>${esc(label)} &middot; ${esc(item.publisher||item.evidence_id)}</b><p>${esc(item.quote||'\u539f\u6587\u5f85\u8865')}</p><small>${esc(item.locator||'\u5b9a\u4f4d\u7b26\u5f85\u8865')} &middot; ${esc(item.evidence_scope||'')}</small><br><a class="evidence-link" href="${esc(item.url)}" target="_blank" rel="noopener noreferrer">\u6253\u5f00\u5b98\u65b9\u8bc1\u636e</a></div>`).join('');
}

function renderMacroPaths(event){
  const filtered=filterPathSet(event.macro_transmission_paths||[],'macro');
  if(!filtered.paths.length)return '<div class="empty">\u5b8f\u89c2\u5e02\u573a\u94fe\u5f85\u751f\u6210\u3002</div>';
  const cards=filtered.paths.map(path=>{
    const indicator=path.market_indicator||{},channel=path.channel||{},h=path.expected_path||{};
    const contexts=(path.timeline_contexts||[]).map(item=>`<li>${esc(item.occurred_at||'\u65f6\u95f4\u5f85\u8865')} &middot; ${esc(item.event_title_zh)}</li>`).join('');
    const eventEvidence=macroEvidenceHtml(path.event_fact_evidence,'\u4e8b\u4ef6\u4e8b\u5b9e\u8bc1\u636e');
    const mechanismEvidence=macroEvidenceHtml(path.mechanism_evidence,'\u673a\u5236\u8f85\u52a9\u8bc1\u636e');
    const reviewText=(path.raw_edges||[]).map(item=>item.review?.rationale_zh).filter(Boolean).filter((value,index,array)=>array.indexOf(value)===index).join('\uff1b');
    return `<article class="transmission-card macro"><header class="transmission-card-head"><div><span class="eyebrow">${esc(path.macro_path_id)}</span><h3>${esc(path.event_title_zh)} \u5982\u4f55\u4f20\u5bfc\u81f3 ${esc(indicator.name_zh)}</h3><p>${esc(path.event_summary_zh)}</p></div><span class="chip warn">${esc((path.binding_statuses||[]).map(status).join('\u3001'))}</span></header><div class="transmission-flow-wrap"><div class="transmission-flow macro-flow"><div class="transmission-step"><small>\u5177\u4f53\u4e8b\u4ef6\u4e0e\u65f6\u95f4</small><b>${esc(path.event_title_zh)}</b><p>${esc(path.event_summary_zh)}</p><div class="chips"><span class="chip">${esc((path.anchor_fast_node_ids||[]).join('\u3001'))}</span></div></div><div class="transmission-arrow">&rarr;</div><div class="transmission-step"><small>\u6709\u65b9\u5411\u7684\u4f20\u5bfc\u6e20\u9053</small><b>${esc(channel.direction_label_zh)}</b><p>${esc(channel.economic_meaning_zh)}</p></div><div class="transmission-arrow">&rarr;</div><div class="transmission-step"><small>\u4e2d\u6587\u5e02\u573a\u6307\u6807</small><b>${esc(indicator.name_zh)}</b><span class="macro-indicator-code">${esc(indicator.code)} &middot; ${esc(indicator.unit_zh)}</span><p>${esc(indicator.economic_meaning_zh)}</p><p><b>\u9884\u671f\u65b9\u5411\uff1a</b>${esc(indicator.direction_interpretation_zh)}</p><div class="macro-directions"><span class="chip">\u5373\u65f6 ${esc(direction(h.IMMEDIATE))}</span><span class="chip">\u77ed\u671f ${esc(direction(h.SHORT_TERM))}</span><span class="chip">\u4e2d\u671f ${esc(direction(h.MEDIUM_TERM))}</span></div></div></div></div><div class="transmission-card-meta"><div><b>\u751f\u6548\u6761\u4ef6</b>${esc((path.conditions||[]).join('\uff1b')||'\u5f85\u8865')}</div><div><b>\u5931\u6548\u6761\u4ef6</b>${esc((path.invalidation_conditions||[]).join('\uff1b')||'\u5f85\u8865')}</div><div><b>\u53cd\u8bc1\u4e0e\u7ade\u4e89\u89e3\u91ca</b>${esc((path.counterevidence||[]).join('\uff1b')||'\u672a\u767b\u8bb0')}</div></div><details class="raw-details"><summary>\u8bc1\u636e\u3001\u5e95\u5c42\u7ed1\u5b9a\u4e0e\u6280\u672f\u8be6\u60c5</summary><div class="raw-details-body"><div class="transmission-evidence">${eventEvidence}${mechanismEvidence}</div><p><b>\u591a\u951a\u70b9\u4e0a\u4e0b\u6587:</b></p><ul>${contexts||'<li>\u65e0</li>'}</ul><p><b>binding_ids:</b> <code>${esc((path.binding_ids||[]).join('\u3001'))}</code></p><p><b>edge_ids:</b> <code>${esc((path.edge_ids||[]).join('\u3001'))}</code></p><p><b>node_ids:</b> <code>${esc((path.node_ids||[]).join('\u3001'))}</code></p><p><b>\u7f6e\u4fe1\u5ea6:</b> ${fmt(path.confidence)} &middot; <b>\u8fb9\u8bc1\u636e\u8303\u56f4:</b> ${esc((path.edge_support_statuses||[]).join('\u3001'))}</p><p><b>\u5ba1\u6838\u8bf4\u660e:</b> ${esc(reviewText||'\u5f85\u4eba\u5de5\u9010\u8fb9\u5ba1\u6838')}</p></div></details></article>`;
  }).join('');
  const unresolved=(event.unresolved_macro_edges||[]);
  const unresolvedHtml=unresolved.length?`<details class="raw-details"><summary>${unresolved.length} \u6761\u65e0\u6cd5\u7ec4\u6210\u5b8c\u6574\u8def\u5f84\u7684\u7ed1\u5b9a</summary><div class="raw-details-body">${unresolved.map(item=>`<p><code>${esc(item.binding_id)}</code> &middot; ${esc(item.from_node_id)} &rarr; ${esc(item.to_node_id)} &middot; ${esc(item.unresolved_reason)}</p>`).join('')}</div></details>`:'';
  return `${filtered.note?`<div class="filter-note">${esc(filtered.note)}</div>`:''}<div class="transmission-stack">${cards}${unresolvedHtml}</div>`;
}

function renderTransmission(event){return state.transmissionMode==='macro'?renderMacroPaths(event):renderOperatingPaths(event)}
function renderIndustries(event){return event.industries.map(industry=>`<button class="industry-button ${state.industryId===industry.industry_id?'active':''}" data-industry="${esc(industry.industry_id)}"><b>${esc(industry.industry_name)}</b><br><small>${industry.company_ids.length} 家公司 · ${esc(status(industry.classification_status))}</small></button>`).join('')||'<div class="empty">行业映射待补。</div>'}
function directionClass(value){return value==='POSITIVE'?'positive':value==='NEGATIVE'?'negative':''}
function renderCompanies(event){let companies=event.companies;if(state.industryId)companies=companies.filter(company=>(company.industry_classification?.sw1_id||'UNKNOWN')===state.industryId);return companies.map(company=>{const h=company.direction?.horizons||{};return `<button class="company-button ${state.companyId===company.company_id?'active':''}" data-company="${esc(company.company_id)}"><h3>${esc(company.company_name)} <small>${esc(company.company_code)}</small></h3><p>${esc(company.industry||'行业待映射')}</p><div class="directions"><span class="direction ${directionClass(h.IMMEDIATE)}">即时<br>${esc(direction(h.IMMEDIATE))}</span><span class="direction ${directionClass(h.SHORT_TERM)}">短期<br>${esc(direction(h.SHORT_TERM))}</span><span class="direction ${directionClass(h.MEDIUM_TERM)}">中期<br>${esc(direction(h.MEDIUM_TERM))}</span></div><span class="chips"><span class="chip warn">${esc(status(company.direction?.review_status))}</span><span class="chip">${esc(status(company.dossier?.dossier_status))}</span></span></button>`}).join('')||'<div class="empty">该筛选下没有公司。</div>'}
function chartSvg(company){const rel=company.relative_window?.observations||{};const points=horizons.map(([key,label])=>{const item=rel[key];if(!item)return null;const c=item.formula_inputs?.company||[];const m=item.formula_inputs?.market||[];return {label,company:c[0]&&c[1]!=null?100*c[1]/c[0]:null,market:m[0]&&m[1]!=null?100*m[1]/m[0]:null}}).filter(Boolean);const values=points.flatMap(p=>[p.company,p.market]).filter(v=>v!=null);if(!values.length)return '<div class="empty">图表数据待补。</div>';let min=Math.min(...values),max=Math.max(...values);if(max-min<2){min-=1;max+=1}const x=i=>55+i*(660/Math.max(1,points.length-1));const y=v=>215-(v-min)/(max-min)*175;const poly=key=>points.filter(p=>p[key]!=null).map((p,i)=>`${x(i)},${y(p[key])}`).join(' ');return `<svg viewBox="0 0 760 250" role="img" aria-label="公司与沪深300标准化走势"><g stroke="#e1e5e2" stroke-width="1"><line x1="55" y1="40" x2="715" y2="40"/><line x1="55" y1="127" x2="715" y2="127"/><line x1="55" y1="215" x2="715" y2="215"/></g><polyline fill="none" stroke="#a63f35" stroke-width="3" points="${poly('company')}"/><polyline fill="none" stroke="#236b66" stroke-width="3" points="${poly('market')}"/>${points.map((p,i)=>`<text x="${x(i)}" y="238" text-anchor="middle" font-size="11" fill="#667175">${p.label}</text>`).join('')}<text x="8" y="44" font-size="11" fill="#667175">${max.toFixed(1)}</text><text x="8" y="218" font-size="11" fill="#667175">${min.toFixed(1)}</text></svg>`}
function marketTable(company){const market=company.market_window?.observations||{},rel=company.relative_window?.observations||{};return horizons.map(([key,label])=>{const m=market[key]||{},r=rel[key]||{};return `<tr><td>${label}</td><td>${esc(m.actual_date||'数据待补')}</td><td>${fmt(m.forward_adjusted_close)}</td><td>${pct(m.absolute_return)}</td><td>${fmt(r.formula_inputs?.market?.[1])}</td><td>${pct(r.market_relative_return)}</td><td>${esc(status(r.industry_status))}</td></tr>`}).join('')}
function evidenceHtml(company){const rows=company.evidence||[];if(!rows.length)return '<div class="empty">公司证据待补。</div>';return rows.slice(0,10).map(row=>`<div class="evidence-item"><b>${esc(row.document_title||row.claim_type)}</b><p>${esc(row.original_quote||'引文待补')}</p><small>${esc(row.page_or_section_locator||'定位待补')} · ${esc(row.published_at||'日期待补')} · ${esc(status(row.review_status))}</small><br><a class="evidence-link" href="${esc(row.source_url)}" target="_blank" rel="noopener noreferrer">打开官方披露</a></div>`).join('')}
function confounderHtml(company){const record=company.confounders||{},items=record.registered_confounders||[];if(!items.length)return `<div class="empty">公告标题检索未发现高风险候选，正文检索与公司级反证仍待完成。当前等级：${esc(status(record.overall_grade))}。</div>`;return items.map(item=>`<div class="confounder-item"><b>${esc(item.quote)}</b><p>${esc(item.mechanism)}</p><small>${esc(item.first_public_at)} · 影响窗口 ${esc((item.affected_windows||[]).join('、'))} · ${esc(status(item.review_status))}</small><br><a class="evidence-link" href="${esc(item.source_url)}" target="_blank" rel="noopener noreferrer">打开巨潮资讯公告</a></div>`).join('')}
const mechanismLabels={EVENT_FACT:'事件事实',BEHAVIOR_OR_POLICY_CHANGE:'行为或政策变化',OBSERVABLE_OPERATING_VARIABLE:'可观测经营变量',INDUSTRY_REVENUE_OR_COST_VARIABLE:'行业收入或成本变量',COMPANY_BUSINESS_EXPOSURE:'公司业务暴露',DIRECTION_ASSESSMENT:'三期限方向判断',PRICE_AND_CONFOUNDER_VERIFICATION:'价格、混杂与反证验证'};
const closureGates=[
  ['经营机制链',['MECHANISM_CHAIN_INCOMPLETE']],
  ['公司 dossier',['DOSSIER_RESEARCH_INCOMPLETE']],
  ['三期限方向',['DIRECTION_HORIZONS_INCOMPLETE']],
  ['公司/大盘/行业窗口',['COMPANY_WINDOW_INCOMPLETE','INDUSTRY_WINDOW_INCOMPLETE']],
  ['混杂检索',['CONFOUNDER_REVIEW_INCOMPLETE']],
  ['停复牌状态',['SUSPENSION_REVIEW_INCOMPLETE']],
];
function chainEvidenceHtml(node,company,event){
  const links=[];
  for(const id of node.evidence_ids||[]){
    const companyEvidence=(company.evidence||[]).find(item=>item.evidence_id===id);
    if(companyEvidence?.source_url){
      links.push(`<a class="evidence-link" href="${esc(companyEvidence.source_url)}" target="_blank" rel="noopener noreferrer" title="${esc((companyEvidence.original_quote||'').slice(0,240))}">公司官方披露 · ${esc(companyEvidence.page_or_section_locator||id)}</a>`);
      continue;
    }
    let eventEvidence=null;
    for(const timelineNode of event.timeline||[]){
      eventEvidence=(timelineNode.evidence||[]).find(item=>item.source_id===id||item.evidence_id===id);
      if(eventEvidence)break;
    }
    if(eventEvidence?.url){
      links.push(`<a class="evidence-link" href="${esc(eventEvidence.url)}" target="_blank" rel="noopener noreferrer">事件官方证据 · ${esc(eventEvidence.publisher||id)}</a>`);
    }else{
      links.push(`<span class="chip">数据引用 ${esc(id)}</span>`);
    }
  }
  return links.length?`<span class="chips">${links.join('')}</span>`:'';
}
function mechanismChainHtml(company,event){
  const chain=company.mechanism_chain||{};
  if(!chain.nodes?.length)return '<div class="empty">公司专属经营机制链待生成。</div>';
  const timelineNode=(event.timeline||[]).find(item=>item.fast_node_id===chain.timeline_node_id)||{};
  const flow=chain.nodes.map((node,index)=>{
    const directionMeta=node.node_type==='DIRECTION_ASSESSMENT'
      ?`<span class="chips"><span class="chip">即时 ${esc(direction(chain.horizon_directions?.IMMEDIATE))}</span><span class="chip">短期 ${esc(direction(chain.horizon_directions?.SHORT_TERM))}</span><span class="chip">中期 ${esc(direction(chain.horizon_directions?.MEDIUM_TERM))}</span></span>`
      :'';
    const timeMeta=node.node_type==='EVENT_FACT'
      ?`<small>发生时间：${esc(timelineNode.occurred_at||'时间待补')} · 锚点：${esc(chain.timeline_node_id)}</small>`
      :'';
    return `<div class="mechanism-step"><div class="mechanism-index"><span>${index+1}</span></div><div class="mechanism-copy"><b>${esc(mechanismLabels[node.node_type]||node.node_type)}</b><p>${esc(node.statement)}</p>${timeMeta}${directionMeta}${chainEvidenceHtml(node,company,event)}</div></div>`;
  }).join('');
  const metrics=(chain.operating_metrics||[]).map(item=>`<span class="chip">${esc(item.name)} · 单位 ${esc(item.unit)}</span>`).join('');
  return `<div class="mechanism-summary"><p>主链从事件事实连续落到公司经营与价格验证，宏观边仅保留为技术血缘。</p><span class="chip warn">${esc(status(chain.review_status))}</span></div><div class="mechanism-flow">${flow}</div><div class="mechanism-meta"><div><b>可观测指标</b><br>${metrics||'指标待补'}</div><div><b>生效条件</b><br>${esc((chain.conditions||[]).join('；')||'待补')}</div><div><b>失效条件</b><br>${esc((chain.invalidation_conditions||[]).join('；')||'待补')}</div></div>`;
}
function closureMatrix(event){
  const header=closureGates.map(([label])=>`<th>${esc(label)}</th>`).join('');
  const rows=event.companies.map(company=>{
    const blockers=company.completion?.blockers||[];
    const gates=closureGates.map(([,codes])=>{
      const open=codes.some(code=>blockers.includes(code));
      return `<td class="${open?'gate-open':'gate-ready'}">${open?'待补':'候选材料具备'}</td>`;
    }).join('');
    return `<tr><td><b>${esc(company.company_name)}</b><br><small>${esc(company.company_code)} · ${esc(company.completion?.completion_status||'OPEN')}</small></td>${gates}</tr>`;
  }).join('');
  return `<h4>候选闭环矩阵</h4><div class="closure-wrap"><table class="closure-table"><thead><tr><th>公司</th>${header}</tr></thead><tbody>${rows}</tbody></table></div>`;
}
function technicalDetails(company){
  const review=company.binding_review||{},completion=company.completion||{};
  const rejected=(review.rejected_bindings||[]).map(item=>`<li><code>${esc(item.binding_id)}</code>：${esc(item.reason)}</li>`).join('');
  return `<details class="tech-details"><summary>技术详情</summary><div class="tech-body"><p><b>主绑定：</b><code>${esc(review.primary_binding_id||'待补')}</code></p><p><b>次级绑定：</b>${esc((review.secondary_binding_ids||[]).join('、')||'无')}</p><p><b>选择依据：</b>${esc(review.selection_basis||'待补')}</p><p><b>拒绝候选：</b></p><ul>${rejected||'<li>无</li>'}</ul><p><b>完成状态：</b>${esc(completion.completion_status||'OPEN')}；<b>阻塞项：</b>${esc((completion.blockers||[]).join('、')||'无')}</p><p><b>审核边界：</b>${esc(status(review.review_status))} · formal_ready=false · SHA 门禁暂缓</p></div></details>`;
}
function companyDetail(event){
  const company=event.companies.find(item=>item.company_id===state.companyId)||event.companies[0];
  if(!company)return '';
  state.companyId=company.company_id;
  const d=company.direction||{},dos=company.dossier||{},conf=company.confounders||{},completion=company.completion||{};
  return `<div class="detail"><div class="detail-head"><div><span class="eyebrow">${esc(company.mapping_id)} · ${esc(completion.completion_status||'OPEN')}</span><h3>${esc(company.company_name)} · ${esc(company.company_code)}</h3><p>${esc(d.mechanism||'影响机制待补')}</p></div><span class="chip warn">${esc(status(d.review_status))}</span></div><div class="chips"><span class="chip">锚点 ${esc(company.lineage.anchor_id)}</span><span class="chip">行业 ${esc(company.industry||'待映射')}</span><span class="chip warn">混杂 ${esc(status(conf.overall_grade))}</span><span class="chip warn">停复牌 ${esc(status(conf.suspension_status))}</span></div><h4>完整经营机制链</h4>${mechanismChainHtml(company,event)}${technicalDetails(company)}${closureMatrix(event)}<div class="detail-grid"><div><h4>绝对价格与沪深300相对收益</h4><div class="legend"><span><i style="background:#a63f35"></i>公司（T-1=100）</span><span><i style="background:#236b66"></i>沪深300（T-1=100）</span></div><div class="chart-wrap">${chartSvg(company)}</div></div><div><h4>业务暴露与审核边界</h4><p>主 dossier：${esc(status(dos.dossier_status))}；官方文档 ${fmt(dos.official_document_count)} 份。</p><p>${esc(dos.gap_reason||'暂无额外缺口说明')}</p><p><b>生效条件：</b>${esc((company.mechanism_chain?.conditions||d.conditions||[]).join('；')||'待补')}</p><p><b>失效条件：</b>${esc((company.mechanism_chain?.invalidation_conditions||d.invalidation_conditions||[]).join('；')||'待补')}</p></div></div><h4>窗口绝对值与变化</h4><div class="table-wrap"><table class="market-table"><thead><tr><th>窗口</th><th>实际交易日</th><th>公司前复权收盘</th><th>公司收益</th><th>沪深300点位</th><th>相对沪深300</th><th>行业基准</th></tr></thead><tbody>${marketTable(company)}</tbody></table></div><h4>公司官方证据</h4><div class="evidence-list">${evidenceHtml(company)}</div><h4>混杂与反证</h4><div class="notice">当前仅登记公告标题级候选；正文未审项目一律为 UNRESOLVED，仅进入挑战集，不支持干净因果归因。公司级反证检索仍待完成。</div><div class="confounder-list">${confounderHtml(company)}</div></div>`;
}

function bind(event){
  document.querySelectorAll('[data-node]').forEach(node=>{
    node.onclick=()=>{state.nodeId=node.dataset.node;renderMain()};
    node.onkeydown=keyEvent=>{
      if(keyEvent.target!==node||!['Enter',' '].includes(keyEvent.key))return;
      keyEvent.preventDefault();state.nodeId=node.dataset.node;renderMain();
    };
  });
  document.querySelectorAll('.timeline-tech,.timeline-node a').forEach(element=>element.onclick=clickEvent=>clickEvent.stopPropagation());
  document.querySelectorAll('[data-transmission-mode]').forEach(button=>button.onclick=()=>{state.transmissionMode=button.dataset.transmissionMode;renderMain()});
  document.querySelectorAll('[data-path-company]').forEach(button=>button.onclick=()=>{
    state.companyId=button.dataset.pathCompany;
    renderMain();
    requestAnimationFrame(()=>document.querySelector('.company-grid')?.scrollIntoView({behavior:'smooth',block:'start'}));
  });
  document.querySelectorAll('[data-industry]').forEach(button=>button.onclick=()=>{state.industryId=state.industryId===button.dataset.industry?null:button.dataset.industry;state.companyId=null;renderMain()});
  document.querySelectorAll('[data-company]').forEach(button=>button.onclick=()=>{state.companyId=button.dataset.company;renderMain()});
  const showAll=document.getElementById('show-all-paths');
  if(showAll)showAll.onclick=()=>{state.nodeId=null;renderMain()};
}
function renderMain(){const event=currentEvent();if(!state.companyId&&event.companies.length)state.companyId=event.companies[0].company_id;document.getElementById('main').innerHTML=`<section class="hero"><div><span class="eyebrow">${event.event_id.toUpperCase()} · 高质量候选链</span><h1>${esc(event.title)}</h1><p>证据时间线 → 动态传导链 → 行业 → 公司业务暴露 → 方向判断 → 价格窗口 → 相对收益 → 混杂与反证</p></div><div class="hero-status"><b>正式发布：未就绪</b><span>AI 方向与公司公告均需人工复核</span></div></section><div class="metrics"><div class="metric"><b>${event.summary.timeline_count}</b><span>时间线节点</span></div><div class="metric"><b>${event.summary.path_count}</b><span>传导候选边</span></div><div class="metric"><b>${event.industries.length}</b><span>关联行业</span></div><div class="metric"><b>${event.summary.company_count}</b><span>公司评估</span></div></div><div class="notice">本页为候选研究数据。证据存在不等于因果已确认；行业基准、停复牌和公司公告正文的缺口会原样显示。</div><section class="section"><div class="section-head"><h2>事件时间线</h2><p>点击节点联动其锚定的传导边</p></div><div class="timeline">${renderTimeline(event)}</div></section><section class="section"><div class="section-head"><h2>动态传导链</h2><p>即时、短期与中期方向均保持独立审核状态</p></div><div class="transmission-toolbar"><div class="transmission-tabs" role="tablist" aria-label="\u4f20\u5bfc\u94fe\u89c6\u56fe"><button class="transmission-tab ${state.transmissionMode==='operating'?'active':''}" data-transmission-mode="operating" role="tab" aria-selected="${state.transmissionMode==='operating'}">\u7ecf\u8425\u5f71\u54cd\u94fe</button><button class="transmission-tab ${state.transmissionMode==='macro'?'active':''}" data-transmission-mode="macro" role="tab" aria-selected="${state.transmissionMode==='macro'}">\u5b8f\u89c2\u5e02\u573a\u94fe</button></div><button class="plain-button" id="show-all-paths">\u663e\u793a\u5168\u90e8\u8def\u5f84</button></div><div class="path-list">${renderTransmission(event)}</div></section><section class="section"><div class="section-head"><h2>行业影响</h2><p>点击行业筛选公司</p></div><div class="industry-strip">${renderIndustries(event)}</div></section><section class="section"><div class="section-head"><h2>公司影响</h2><p>每个事件固定三家公司，禁止事后按股价挑选</p></div><div class="company-grid">${renderCompanies(event)}</div>${companyDetail(event)}</section><footer class="footer">数据版本 ${esc(DATA.dataset_version)} · formal_ready=false · SHA 门禁暂缓 · 页面不包含隐藏评测标签</footer>`;bind(event)}
function render(){renderSidebar();renderMain()}
document.getElementById('menu').onclick=()=>document.getElementById('sidebar').classList.toggle('open');render();
"""


def render_workbench(bundle: Mapping[str, Any]) -> str:
    if not bundle.get("events"):
        raise ValueError("UI_EVENTS_REQUIRED")
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FinGoose 宏观事件与公司影响工作台</title><link rel="icon" href="data:,"><style>{STYLE}</style><script src="ui_data_bundle.js"></script></head><body><div class="app"><aside class="sidebar" id="sidebar"><div class="brand"><b>FINGOOSE</b><span>宏观事件与公司影响研究工作台</span></div><div class="side-state">高质量候选数据<br>证据、推断与价格结果分层展示</div><div class="side-label">十个宏观事件</div><nav class="event-nav" id="event-nav"></nav><div class="side-foot">50 个时间线节点<br>30 条事件-公司映射<br>所有 AI 方向待人工审核</div></aside><div class="workspace"><header class="topbar"><strong>事件、行业与公司影响链</strong><span>点击事件、节点、行业或公司查看联动证据</span><button class="menu" id="menu" aria-label="打开事件目录">事件目录</button></header><main class="content" id="main"></main></div></div><script>{SCRIPT}</script></body></html>'''


def write_ui(
    root: Path,
    output_root: Path,
    *,
    candidate_root: Path | None = None,
) -> dict[str, Any]:
    bundle = build_ui_bundle(root, candidate_root=candidate_root)
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "ui_data_bundle.js").write_text(
        "window.FINGOOSE_COMPANY_IMPACT_V2="
        + json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    (output_root / "index.html").write_text(
        render_workbench(bundle), encoding="utf-8"
    )
    return bundle["summary"]
