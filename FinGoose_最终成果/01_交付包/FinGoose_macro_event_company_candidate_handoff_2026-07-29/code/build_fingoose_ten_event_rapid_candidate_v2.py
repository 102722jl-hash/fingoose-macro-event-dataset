from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

from fingoose_event_storylines import STORYLINE_SPECS
from fingoose_ten_event_rapid_config import (
    CORE_PATH_SPECS,
    CONFOUNDER_CONFIGS,
    EVENT_CONFIGS,
    MECHANISM_SOURCES,
)
from fingoose_workbench_ui import (
    build_confounder_argument,
    render_workbench,
    ui_copy,
)


RELEASE_TIER = "RAPID_CANDIDATE"
DATASET_VERSION = "fingoose-ten-event-rapid-candidate-v2.0"
WINDOW_LABELS = ["T-1", "T0", "D1", "D3", "D5", "D20"]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _register_source(registry: dict[str, dict[str, Any]], source: dict[str, Any]) -> None:
    source_id = source["source_id"]
    existing = registry.get(source_id)
    if existing and existing.get("url") != source.get("url"):
        raise ValueError(f"conflicting URLs for source_id={source_id}")
    registry[source_id] = source


def build_source_registry(root: Path) -> dict[str, dict[str, Any]]:
    registry: dict[str, dict[str, Any]] = {}

    production_path = (
        root / "data" / "market_event_attribution_v2_candidate" / "source_manifest.jsonl"
    )
    for row in read_jsonl(production_path):
        _register_source(
            registry,
            {
                "source_id": row["evidence_id"],
                "event_id": row.get("event_id"),
                "publisher": row.get("publisher") or "UNKNOWN",
                "source_tier": row.get("source_tier") or "UNKNOWN",
                "url": row.get("source_url"),
                "published_at": row.get("published_at"),
                "title": row.get("title"),
                "locator": row.get("title"),
                "quote": None,
                "evidence_scope": "EVENT_FACT_AND_TIME",
                "visibility": "PUBLIC_PREDICTION",
                "snapshot_path": row.get("snapshot_path"),
            },
        )

    candidate_path = (
        root / "work" / "timeline_fast_candidate_v2" / "candidate_source_manifest.jsonl"
    )
    for row in read_jsonl(candidate_path):
        url = row.get("source_url") or row.get("candidate_url")
        if row.get("decision") != "ACCEPTED" or not url:
            continue
        _register_source(
            registry,
            {
                "source_id": row["candidate_source_id"],
                "event_id": row.get("attachment_node_id", "")[5:13] or None,
                "publisher": row.get("publisher") or "UNKNOWN",
                "source_tier": row.get("source_tier") or "UNKNOWN",
                "url": url,
                "published_at": None,
                "title": None,
                "locator": None,
                "quote": None,
                "evidence_scope": "EVENT_FACT_AND_TIME",
                "visibility": "PUBLIC_PREDICTION",
                "snapshot_path": row.get("snapshot_path"),
            },
        )

    for row in MECHANISM_SOURCES:
        _register_source(registry, deepcopy(row))

    return registry


def _same_day_groups(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    by_date: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        timestamp = node.get("first_public_at")
        if node.get("evidence_status") == "VERIFIED_EXISTING" and timestamp:
            by_date[timestamp[:10]].append(node["fast_node_id"])
    groups = [
        {
            "date": date,
            "node_ids": node_ids,
            "status": "SAME_DAY_UNRESOLVED",
            "reason": "Daily observations cannot identify the marginal effect of same-day nodes.",
        }
        for date, node_ids in sorted(by_date.items())
        if len(node_ids) > 1
    ]
    return {
        "status": "SAME_DAY_UNRESOLVED" if groups else "UNIQUE_DAILY_ANCHOR",
        "groups": groups,
    }


def _timestamp_value(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _chronology_warnings(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    for previous, current in zip(nodes, nodes[1:]):
        previous_time = _timestamp_value(previous.get("first_public_at"))
        current_time = _timestamp_value(current.get("first_public_at"))
        if (
            previous_time is not None
            and current_time is not None
            and current_time < previous_time
        ):
            warnings.append({
                "type": "CURATED_SEQUENCE_TIMESTAMP_INVERSION",
                "previous_node_id": previous["fast_node_id"],
                "previous_first_public_at": previous["first_public_at"],
                "current_node_id": current["fast_node_id"],
                "current_first_public_at": current["first_public_at"],
            })
    return warnings


def _node_matches_activation(
    spec: dict[str, Any],
    node: dict[str, Any],
) -> bool:
    phases = set(spec.get("activation_phases") or [])
    actions = set(spec.get("activation_actions") or [])
    required_tags = set(spec.get("activation_tags") or [])
    node_tags = set(node.get("impact_tags") or [])
    return (
        node.get("phase") in phases
        and node.get("node_action") in actions
        and required_tags.issubset(node_tags)
    )


def _linked_path_ids(node: dict[str, Any]) -> list[str]:
    if node.get("evidence_status") != "VERIFIED_EXISTING":
        return []
    return [
        row["path_id"]
        for row in CORE_PATH_SPECS
        if row["event_id"] == node["event_id"]
        and _node_matches_activation(row, node)
    ]


def _select_path_anchor(
    spec: dict[str, Any],
    nodes: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    matching = [node for node in nodes if _node_matches_activation(spec, node)]
    verified = [
        node
        for node in matching
        if node.get("evidence_status") == "VERIFIED_EXISTING"
        and node.get("source_ids")
    ]
    pending = [
        node
        for node in matching
        if node.get("evidence_status") == "PENDING_EVIDENCE"
    ]
    return (
        min(verified, key=lambda row: row["sequence"]) if verified else None,
        min(pending, key=lambda row: row["sequence"]) if pending else None,
    )


def build_timelines(root: Path) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    path = root / "work" / "timeline_fast_candidate_v2" / "timeline_nodes.jsonl"
    for raw in read_jsonl(path):
        node = deepcopy(raw)
        node["linked_path_ids"] = _linked_path_ids(node)
        node["impact_summary"] = (
            "Pending evidence; no scored path is activated."
            if node.get("evidence_status") == "PENDING_EVIDENCE"
            else "Verified milestone; linked paths are rule-projected candidates."
        )
        grouped[node["event_id"]].append(node)

    timelines: dict[str, dict[str, Any]] = {}
    for event_id, config in EVENT_CONFIGS.items():
        nodes = sorted(grouped[event_id], key=lambda row: row["sequence"])
        primary = [row for row in nodes if row.get("anchor_role") == "PRIMARY"]
        chronology_warnings = _chronology_warnings(nodes)
        timelines[event_id] = {
            "event_id": event_id,
            "title": config["title_zh"],
            "release_tier": RELEASE_TIER,
            "formal_ready": False,
            "primary_anchor_fast_node_id": (
                primary[0]["fast_node_id"] if len(primary) == 1 else None
            ),
            "nodes": nodes,
            "daily_resolution": _same_day_groups(nodes),
            "ordering_basis": "CURATED_SEQUENCE",
            "chronology_warnings": chronology_warnings,
            "chronology_status": (
                "CURATED_SEQUENCE_WITH_TIMESTAMP_INVERSIONS"
                if chronology_warnings
                else "CURATED_SEQUENCE_CHRONOLOGICAL"
            ),
        }
    return timelines


def build_core_paths(
    root: Path,
    sources: dict[str, dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    sources = sources or build_source_registry(root)
    timelines = build_timelines(root)
    grouped: dict[str, list[dict[str, Any]]] = {event_id: [] for event_id in EVENT_CONFIGS}

    for spec in CORE_PATH_SPECS:
        event_id = spec["event_id"]
        nodes = timelines[event_id]["nodes"]
        anchor, pending = _select_path_anchor(spec, nodes)
        if anchor is None:
            fact_evidence: list[str] = []
            anchor_ids: list[str] = []
            anchor_status = (
                "PENDING_EVIDENCE"
                if pending
                else "NO_MATCHING_VERIFIED_ANCHOR"
            )
            candidate_anchor_ids = (
                [pending["fast_node_id"]] if pending else []
            )
            scoring_eligible = False
        else:
            fact_evidence = list(anchor["source_ids"])
            anchor_ids = [anchor["fast_node_id"]]
            anchor_status = anchor["evidence_status"]
            candidate_anchor_ids = []
            scoring_eligible = True

        unresolved = [source_id for source_id in fact_evidence if source_id not in sources]
        unresolved.extend(
            source_id
            for source_id in spec["mechanism_source_ids"]
            if source_id not in sources
        )
        if unresolved:
            raise ValueError(
                f"{spec['path_id']} has unresolved sources: {sorted(set(unresolved))}"
            )

        path = deepcopy(spec)
        path["name"] = path.pop("name_zh")
        path["anchor_fast_node_ids"] = anchor_ids
        path["unverified_candidate_anchor_ids"] = candidate_anchor_ids
        path["anchor_evidence_status"] = anchor_status
        path["scoring_eligible"] = scoring_eligible
        path["event_fact_evidence"] = fact_evidence
        path["mechanism_evidence"] = [
            {
                "source_id": source_id,
                "evidence_scope": sources[source_id]["evidence_scope"],
                "prediction_use": (
                    "EXCLUDED_TO_PREVENT_LEAKAGE"
                    if sources[source_id].get("visibility")
                    == "HIDDEN_FROM_PRIMARY_PREDICTION"
                    else "AVAILABLE_AT_ANCHOR"
                ),
            }
            for source_id in path.pop("mechanism_source_ids")
        ]
        grouped[event_id].append(path)

    return grouped


SERIES_META = {
    "SP500": ("标普 500 指数", "指数点", "风险资产"),
    "VIXCLS": ("VIX 收盘指数", "指数点", "风险规避"),
    "DCOILWTICO": ("WTI 原油现货价", "美元/桶", "能源与增长"),
    "DCOILBRENTEU": ("Brent 原油现货价", "美元/桶", "能源供应风险"),
    "DHHNGSP": ("Henry Hub 天然气现货价", "美元/百万英热单位", "天然气供应风险代理"),
    "DGS10": ("美国 10 年期国债收益率", "%", "利率预期"),
    "DTWEXBGS": ("美元广义贸易加权指数", "指数点", "美元流动性"),
    "DEXCHUS": ("人民币兑美元", "人民币/美元", "人民币汇率"),
    "DEXJPUS": ("日元兑美元", "日元/美元", "日元汇率"),
}


def _display_point(point: dict[str, Any], alias: str | None = None) -> dict[str, Any]:
    result = {
        "date": point.get("date"),
        "value": point.get("value"),
        "raw_change": point.get("raw_change"),
        "standardized_change": point.get("standardized_change"),
        "relative_change": point.get("relative_change"),
        "empirical_percentile": None,
        "percentile_status": "DEFERRED_VALIDATION",
    }
    if alias:
        result["observation_alias"] = alias
    return result


def _market_formulas(metric_type: str, benchmark: str | None) -> dict[str, str]:
    raw_change = (
        "(V_h - V_T-1) * 100 basis points"
        if metric_type == "yield_basis_points"
        else "(V_h - V_T-1) / abs(V_T-1) * 100%"
    )
    return {
        "raw_change": raw_change,
        "standardized_change": (
            "raw_change / (stddev(previous 60 session daily changes) "
            "* sqrt(session_distance))"
        ),
        "relative_change": (
            f"raw_change - {benchmark} raw_change on the same dates"
            if benchmark
            else "null: no ex-ante comparable benchmark was assigned"
        ),
        "empirical_percentile": "DEFERRED_VALIDATION",
    }


def _project_market_row(
    row: dict[str, Any],
    *,
    asset_tier: str,
) -> dict[str, Any]:
    series_id = row["series_id"]
    series_name, unit, role = SERIES_META[series_id]
    baseline = {
        **row["baseline"],
        "raw_change": 0.0,
        "standardized_change": 0.0,
        "relative_change": 0.0 if row.get("benchmark_series_id") else None,
        "empirical_percentile": None,
    }
    d1 = row["windows"]["D1"]
    display_windows = {
        "T-1": _display_point(baseline),
        "T0": _display_point(d1, "D1_CLOSE"),
        "D1": _display_point(d1, "T0_CLOSE"),
        "D3": _display_point(row["windows"]["D3"]),
        "D5": _display_point(row["windows"]["D5"]),
        "D20": _display_point(row["windows"]["D20"]),
    }
    return {
        "event_id": row["event_id"],
        "anchor_fast_node_id": None,
        "series_id": series_id,
        "series_name": series_name,
        "unit": unit,
        "asset_role": role,
        "asset_tier": asset_tier,
        "metric_type": row["metric_type"],
        "benchmark_series_id": row.get("benchmark_series_id"),
        "timezone": row.get("timezone"),
        "calendar_id": row.get("calendar_id"),
        "observation_cutoff": row.get("observation_cutoff"),
        "t0": row.get("t0"),
        "daily_t0_rule": "T0_CLOSE_EQUALS_D1",
        "daily_resolution_note": (
            "Daily data provide one event-date close; T0 and D1 are aliases, "
            "not independent observations."
        ),
        "estimation": row.get("estimation"),
        "display_windows": display_windows,
        "formulas": _market_formulas(
            row["metric_type"],
            row.get("benchmark_series_id"),
        ),
        "observation_source": {
            **(row.get("observation_source") or {}),
            "sha_gate": "DEFERRED_BY_USER_FOR_RAPID_CANDIDATE",
        },
        "percentile_status": "DEFERRED_VALIDATION",
        "source_calculation_basis": row.get("calculation_basis"),
    }


def build_market_packages(root: Path) -> dict[str, list[dict[str, Any]]]:
    production_rows = read_jsonl(
        root / "data" / "market_event_attribution_v2_candidate" / "market_windows.jsonl"
    )
    production = {
        (row["event_id"], row["series_id"]): row
        for row in production_rows
    }
    packages: dict[str, list[dict[str, Any]]] = {}

    event02_extensions: dict[str, dict[str, Any]] = {}
    from build_fingoose_event_02_rapid_candidate_v2 import _build_market_windows

    for row in _build_market_windows(root):
        if row["series_id"] not in {"DHHNGSP", "DGS10"}:
            continue
        extension = deepcopy(row)
        extension["asset_tier"] = (
            "CORE" if row["series_id"] == "DHHNGSP" else "OPTIONAL_EXTENSION"
        )
        extension["percentile_status"] = "DEFERRED_VALIDATION"
        for point in extension["display_windows"].values():
            point["empirical_percentile"] = None
            point["percentile_status"] = "DEFERRED_VALIDATION"
        event02_extensions[row["series_id"]] = extension

    timelines = build_timelines(root)
    for event_id, config in EVENT_CONFIGS.items():
        rows: list[dict[str, Any]] = []
        for series_id in config["core_series_ids"]:
            if event_id == "event-02" and series_id == "DHHNGSP":
                row = deepcopy(event02_extensions[series_id])
            else:
                key = (event_id, series_id)
                if key not in production:
                    raise ValueError(f"missing production market row: {key}")
                row = _project_market_row(production[key], asset_tier="CORE")
            row["anchor_fast_node_id"] = timelines[event_id][
                "primary_anchor_fast_node_id"
            ]
            rows.append(row)
        for series_id in config["optional_series_ids"]:
            if event_id == "event-02" and series_id in event02_extensions:
                row = deepcopy(event02_extensions[series_id])
                row["anchor_fast_node_id"] = timelines[event_id][
                    "primary_anchor_fast_node_id"
                ]
                rows.append(row)
        packages[event_id] = rows

    return packages

def build_confounders() -> dict[str, dict[str, Any]]:
    return deepcopy(CONFOUNDER_CONFIGS)


def build_stage_mappings(
    timelines: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    path_by_id = {row["path_id"]: row for row in CORE_PATH_SPECS}
    mappings: dict[str, dict[str, Any]] = {}
    for event_id, timeline in timelines.items():
        primary = next(
            node
            for node in timeline["nodes"]
            if node.get("anchor_role") == "PRIMARY"
        )
        primary_date = (primary.get("first_public_at") or "")[:10]
        primary_sequence = primary["sequence"]
        node_mappings: list[dict[str, Any]] = []
        for node in timeline["nodes"]:
            node_date = (node.get("first_public_at") or "")[:10]
            if node.get("evidence_status") == "PENDING_EVIDENCE":
                market_status = "PENDING_EVIDENCE"
            elif node.get("anchor_role") == "PRIMARY":
                market_status = "PRIMARY_ANCHOR"
            elif node_date and node_date == primary_date:
                market_status = "SAME_DAY_UNRESOLVED"
            elif node["sequence"] < primary_sequence:
                market_status = "NOT_COMPUTED"
            else:
                market_status = "OUTSIDE_PRIMARY_ANCHOR_WINDOW"

            path_ids = node.get("linked_path_ids") or []
            series_ids = sorted({
                series_id
                for path_id in path_ids
                for series_id in path_by_id[path_id]["asset_series_ids"]
                if series_id in EVENT_CONFIGS[event_id]["core_series_ids"]
            })
            node_mappings.append({
                "fast_node_id": node["fast_node_id"],
                "phase": node["phase"],
                "node_action": node["node_action"],
                "path_ids": path_ids,
                "series_ids": series_ids,
                "market_window_status": market_status,
            })
        mappings[event_id] = {
            "event_id": event_id,
            "mapping_rule": (
                "node -> rule-matched core paths -> preselected core series"
            ),
            "node_mappings": node_mappings,
        }
    return mappings

def build_storylines(
    timelines: dict[str, dict[str, Any]],
    paths_by_event: dict[str, list[dict[str, Any]]],
    markets_by_event: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for event_id, specs in STORYLINE_SPECS.items():
        timeline = timelines[event_id]
        nodes = {row["fast_node_id"]: row for row in timeline["nodes"]}
        paths = {row["path_id"]: row for row in paths_by_event[event_id]}
        market_ids = {row["series_id"] for row in markets_by_event[event_id]}
        steps: list[dict[str, Any]] = []
        for raw_spec in specs:
            spec = deepcopy(raw_spec)
            refs = [nodes[node_id] for node_id in spec["evidence_node_ids"]]
            coverage = spec.pop("coverage")
            precision = spec.pop("time_precision_override")
            has_pending = any(
                row.get("evidence_status") == "PENDING_EVIDENCE"
                for row in refs
            )
            if has_pending or coverage == "PENDING":
                evidence_status = "PENDING_EVIDENCE"
            elif coverage == "DIRECT":
                evidence_status = "SUPPORTED"
            else:
                evidence_status = "PARTIALLY_SUPPORTED"

            linked_path_ids = list(dict.fromkeys(
                path_id
                for row in refs
                for path_id in row.get("linked_path_ids", [])
                if path_id in paths
            ))
            action = refs[-1].get("node_action")
            activated = linked_path_ids if action == "STARTS" else []
            amplified = linked_path_ids if action == "AMPLIFIES" else []
            weakened = linked_path_ids if action in {"WEAKENS", "CALMS"} else []
            series_ids = list(dict.fromkeys(
                series_id
                for path_id in linked_path_ids
                for series_id in paths[path_id].get("asset_series_ids", [])
                if series_id in market_ids
            ))
            public_times = [
                row.get("first_public_at")
                for row in refs
                if row.get("first_public_at")
            ]
            if precision == "UNKNOWN" or not public_times:
                period_start = period_end = None
            elif precision == "DATE":
                dates = [value[:10] for value in public_times]
                period_start, period_end = min(dates), max(dates)
            else:
                period_start, period_end = min(public_times), max(public_times)

            if evidence_status == "PENDING_EVIDENCE":
                boundary = "核心事实仍待补证，当前只保留候选叙事，不进入干净归因评分。"
            elif evidence_status == "PARTIALLY_SUPPORTED":
                boundary = "关联证据支持核心事实；精确时刻或部分阶段解释仍需补证。"
            else:
                boundary = "关联证据支持事件事实；前后状态与阶段意义属于可追溯的研究归纳。"
            spec.update({
                "period_start": period_start,
                "period_end": period_end,
                "time_precision": precision,
                "evidence_status": evidence_status,
                "evidence_boundary_cn": boundary,
                "activated_path_ids": activated,
                "amplified_path_ids": amplified,
                "weakened_path_ids": weakened,
                "market_series_ids": series_ids,
            })
            steps.append(spec)
        result[event_id] = {
            "event_id": event_id,
            "title": timeline["title"],
            "ordering_basis": "CURATED_STORY_SEQUENCE",
            "steps": steps,
        }
    return result


EVENT_PAGE_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__PAGE_TITLE__</title>
<style>
:root{--ink:#172027;--muted:#65727b;--line:#d8dee2;--paper:#f5f7f6;--panel:#fff;--red:#b83d36;--green:#18705a;--amber:#99620f;--blue:#276a8c}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:"Microsoft YaHei",Arial,sans-serif;letter-spacing:0}
header{background:#182229;color:#fff;border-bottom:4px solid var(--red);padding:18px 24px}header a{color:#c8d6de;text-decoration:none;font-size:12px}
h1{font-size:23px;line-height:1.35;margin:8px 0 4px}h2{font-size:17px;margin:0 0 14px}h3{font-size:14px;margin:0 0 7px}.wrap{max-width:1320px;margin:auto;padding:20px}
.status{display:flex;gap:7px;flex-wrap:wrap;margin-top:12px}.badge{font-size:11px;border:1px solid #65737c;padding:4px 7px}.warning{color:#ffd38d}
.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-bottom:16px}.kpi{background:#fff;border:1px solid var(--line);padding:10px 12px}.kpi b{display:block;font-size:20px}
.tabs{display:flex;border-bottom:1px solid var(--line);margin-bottom:16px;overflow-x:auto}.tabs button{border:0;background:none;padding:10px 13px;white-space:nowrap;font-weight:700;cursor:pointer}.tabs button.active{color:var(--red);border-bottom:3px solid var(--red)}
.view{display:none}.view.active{display:block}.grid{display:grid;grid-template-columns:minmax(330px,.9fr) minmax(460px,1.4fr);gap:16px}.panel{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:15px}
.timeline{border-left:2px solid #94a0a7;margin-left:7px;padding-left:18px}.node{position:relative;border:0;background:transparent;width:100%;text-align:left;padding:0 0 19px;cursor:pointer;color:inherit}.node:before{content:"";position:absolute;left:-24px;top:5px;width:10px;height:10px;border-radius:50%;background:var(--blue)}.node.pending:before{background:var(--amber)}.node.selected h3{color:var(--red)}.meta{font-size:11px;color:var(--muted);margin-bottom:5px}.fact{font-size:13px;line-height:1.55}.impact{font-size:12px;line-height:1.5;color:#3e4b53;margin-top:7px}
.path{border-top:1px solid var(--line);padding:14px 0}.path:first-child{border-top:0;padding-top:0}.path.focus{outline:2px solid #d8a39e;outline-offset:5px}.chain{font-family:Consolas,monospace;font-size:12px;color:#24536b;overflow-wrap:anywhere}.directions{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}.directions span{font-size:11px;border:1px solid var(--line);padding:3px 5px}
.citation-group{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:8px}.citation-label{font-size:11px;font-weight:700;color:#4a5860}.citation-link{display:inline-flex;max-width:100%;font-size:11px;line-height:1.35;padding:3px 6px;border:1px solid #bac8d0;border-radius:4px;background:#f5fafc;color:#155d84;text-decoration:none;overflow-wrap:anywhere}.citation-link.mechanism{background:#fff9ed;border-color:#d3c19e;color:#725019}.citation-empty{font-size:11px;color:var(--muted);font-style:italic}
.note{border-left:3px solid var(--amber);background:#fff8e9;padding:9px 11px;font-size:12px;line-height:1.5;margin:10px 0}.source{border-top:1px solid var(--line);padding:10px 0}.source:first-child{border-top:0}.link-button{border:1px solid #aebbc3;background:#fff;padding:5px 7px;margin:3px 4px 3px 0;cursor:pointer;color:#1b5f82}
select{padding:8px;border:1px solid #aab5bc;background:#fff;max-width:100%}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:12px;margin-top:10px}th,td{border-bottom:1px solid var(--line);padding:8px 7px;text-align:right;white-space:nowrap}th:first-child,td:first-child{text-align:left}
@media(max-width:760px){header{padding:15px}.wrap{padding:10px}.grid{grid-template-columns:1fr}.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}h1{font-size:20px}.panel{padding:12px}}
</style>
</head>
<body>
<header><a href="../../index.html">返回十事件总览</a><h1>__EVENT_HEADING__</h1><div class="status"><span class="badge">RAPID_CANDIDATE</span><span class="badge">formal_ready=false</span><span class="badge warning">核心路径均为 PROPOSED</span></div></header>
<main class="wrap">
<div class="kpis"><div class="kpi"><b id="node-count"></b>时间线节点</div><div class="kpi"><b id="path-count"></b>核心候选路径</div><div class="kpi"><b id="series-count"></b>市场序列</div><div class="kpi"><b>0</b>已确认路径</div></div>
<nav class="tabs"><button class="active" data-view="timeline">事件时间线</button><button data-view="paths">动态传导链</button><button data-view="market">绝对值与变化</button><button data-view="evidence">证据与混杂</button></nav>
<section id="timeline" class="view active"><div class="grid"><div class="panel"><h2>证据时间线</h2><div id="chronology-note" class="note"></div><div id="timeline-list" class="timeline"></div></div><div class="panel"><h2>节点联动</h2><div id="node-detail"></div></div></div></section>
<section id="paths" class="view"><div class="panel"><h2>动态传导链</h2><div class="note">CORE_REVIEWED 仅表示已选为核心候选；未完成人工确认，状态仍为 PROPOSED。</div><div id="path-list"></div></div></section>
<section id="market" class="view"><div class="panel"><h2>核心资产窗口</h2><select id="series"></select><div class="note"><b>T0_CLOSE_EQUALS_D1</b><br>日频 T0 与 D1 是同一事件日收盘观测，不是两个独立数据点。</div><div class="scroll"><table><thead><tr><th>窗口</th><th>日期</th><th>绝对值</th><th>原始变化</th><th>标准化变化</th><th>相对变化</th><th>分位状态</th></tr></thead><tbody id="market-body"></tbody></table></div><div id="formula" class="note"></div></div></section>
<section id="evidence" class="view"><div class="grid"><div class="panel"><h2>混杂与竞争解释</h2><div id="confounders"></div></div><div class="panel"><h2>证据来源</h2><div id="sources"></div></div></div></section>
</main>
<script id="data" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById("data").textContent);
const esc=s=>String(s??"UNKNOWN").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const sourceById=Object.fromEntries(D.sources.map(s=>[s.source_id,s]));
function citationLinks(refs,role){
  const ids=(refs||[]).map(ref=>typeof ref==="string"?ref:ref.source_id);
  if(!ids.length)return '<span class="citation-empty">暂无已验证引用</span>';
  return ids.map(id=>{
    const source=sourceById[id];
    if(!source||!source.url)return '<span class="citation-empty">UNKNOWN · '+esc(id)+'</span>';
    const post=source.visibility==="HIDDEN_FROM_PRIMARY_PREDICTION";
    const label=post?"事后机制验证":(role==="mechanism"?"机制":"事实与时间");
    return '<a class="citation-link '+role+'" href="'+esc(source.url)+'" target="_blank" rel="noopener noreferrer">↗ '+esc(source.publisher)+' · '+label+'</a>';
  }).join("");
}
function activate(view){
  document.querySelectorAll(".tabs button,.view").forEach(x=>x.classList.remove("active"));
  document.querySelector('.tabs button[data-view="'+view+'"]').classList.add("active");
  document.getElementById(view).classList.add("active");
}
document.querySelectorAll(".tabs button").forEach(button=>button.onclick=()=>activate(button.dataset.view));
document.getElementById("node-count").textContent=D.timeline.nodes.length;
document.getElementById("path-count").textContent=D.paths.length;
document.getElementById("series-count").textContent=D.windows.length;
const chronologyWarnings=D.timeline.chronology_warnings||[];
document.getElementById("chronology-note").innerHTML=chronologyWarnings.length
  ? '<b>叙事顺序存在公开时间倒序</b><br>'+chronologyWarnings.map(row=>
      esc(row.previous_node_id)+' ('+esc(row.previous_first_public_at)+') → '
      +esc(row.current_node_id)+' ('+esc(row.current_first_public_at)+')'
    ).join("<br>")
  : '<b>叙事顺序</b><br>当前序号与首次公开时间一致。';
function renderNodeDetail(node){
  const mapping=D.mapping.node_mappings.find(row=>row.fast_node_id===node.fast_node_id);
  const pathButtons=(mapping.path_ids||[]).map(id=>'<button class="link-button" data-path="'+esc(id)+'">'+esc(id)+'</button>').join("")||"无激活路径";
  const seriesButtons=(mapping.series_ids||[]).map(id=>'<button class="link-button" data-series="'+esc(id)+'">'+esc(id)+'</button>').join("")||"无市场窗口";
  document.getElementById("node-detail").innerHTML='<div class="meta">'+esc(node.fast_node_id)+' · '+esc(mapping.market_window_status)+'</div><h3>'+esc(node.node_action)+' / '+esc(node.phase)+'</h3><div class="fact">'+esc(node.fact)+'</div><div class="note">'+esc(node.impact_summary)+'</div><div class="source"><b>联动路径</b><div>'+pathButtons+'</div></div><div class="source"><b>联动资产</b><div>'+seriesButtons+'</div></div><div class="citation-group"><span class="citation-label">事实来源</span>'+citationLinks(node.source_ids,"fact")+'</div>';
  document.querySelectorAll("[data-path]").forEach(button=>button.onclick=()=>{activate("paths");document.querySelectorAll(".path").forEach(x=>x.classList.remove("focus"));const target=document.getElementById(button.dataset.path);if(target){target.classList.add("focus");target.scrollIntoView({behavior:"smooth",block:"center"});}});
  document.querySelectorAll("[data-series]").forEach(button=>button.onclick=()=>{activate("market");document.getElementById("series").value=button.dataset.series;renderMarket();});
}
document.getElementById("timeline-list").innerHTML=D.timeline.nodes.map((node,index)=>'<button class="node '+(node.evidence_status==="PENDING_EVIDENCE"?"pending ":"")+(index===0?"selected":"")+'" data-node="'+esc(node.fast_node_id)+'"><div class="meta">'+esc(node.fast_node_id)+' · '+esc(node.phase)+' · '+esc(node.first_public_at)+'</div><h3>'+esc(node.node_action)+' / '+esc(node.evidence_status)+'</h3><div class="fact">'+esc(node.fact)+'</div><div class="citation-group"><span class="citation-label">事实来源</span>'+citationLinks(node.source_ids,"fact")+'</div></button>').join("");
document.querySelectorAll("[data-node]").forEach(button=>button.onclick=()=>{document.querySelectorAll("[data-node]").forEach(x=>x.classList.remove("selected"));button.classList.add("selected");renderNodeDetail(D.timeline.nodes.find(node=>node.fast_node_id===button.dataset.node));});
renderNodeDetail(D.timeline.nodes[0]);
document.getElementById("path-list").innerHTML=D.paths.map(path=>'<article class="path" id="'+esc(path.path_id)+'"><div class="meta">'+esc(path.path_id)+' · '+esc(path.selection_status)+' · '+esc(path.confirmation_status)+'</div><h3>'+esc(path.name)+'</h3><div class="chain">'+esc(path.chain.join(" → "))+'</div><div class="directions">'+Object.entries(path.expected_direction).map(([key,value])=>'<span>'+esc(key)+': '+esc(value)+'</span>').join("")+'</div><div class="meta">时滞：'+esc(path.lag.minimum)+' 至 '+esc(path.lag.maximum)+'</div><div class="meta">条件：'+esc(path.conditions.join("；"))+'</div><div class="meta">失效：'+esc(path.invalidation_conditions.join("；"))+'</div><div class="impact">反证：'+esc(path.counterevidence.join("；"))+'</div><div class="citation-group"><span class="citation-label">事件事实依据</span>'+citationLinks(path.event_fact_evidence,"fact")+'</div><div class="citation-group"><span class="citation-label">机制依据</span>'+citationLinks(path.mechanism_evidence,"mechanism")+'</div></article>').join("");
const select=document.getElementById("series");
select.innerHTML=D.windows.map(row=>'<option value="'+esc(row.series_id)+'">'+esc(row.series_name)+' · '+esc(row.asset_tier)+'</option>').join("");
const fmt=value=>value==null?"UNKNOWN":Number(value).toLocaleString("zh-CN",{maximumFractionDigits:4});
function renderMarket(){
  const row=D.windows.find(item=>item.series_id===select.value)||D.windows[0];
  document.getElementById("market-body").innerHTML=Object.entries(row.display_windows).map(([label,point])=>'<tr><td>'+label+'</td><td>'+esc(point.date)+'</td><td>'+fmt(point.value)+' '+esc(row.unit)+'</td><td>'+fmt(point.raw_change)+'</td><td>'+fmt(point.standardized_change)+'</td><td>'+fmt(point.relative_change)+'</td><td>'+esc(point.percentile_status||"DEFERRED_VALIDATION")+'</td></tr>').join("");
  document.getElementById("formula").innerHTML="<b>计算公式</b><br>"+esc(row.formulas.raw_change)+"<br>"+esc(row.formulas.standardized_change)+"<br>"+esc(row.formulas.relative_change);
}
select.onchange=renderMarket;renderMarket();
document.getElementById("confounders").innerHTML='<div class="note"><b>'+esc(D.confounders.clean_attribution_decision)+'</b><br>'+esc(D.confounders.reason)+'</div>'+D.confounders.items.map(item=>'<div class="source"><b>'+esc(item.level)+' · '+esc(item.confounder_id)+'</b><div class="impact">'+esc(item.description)+'</div><div class="meta">影响窗口：'+esc(item.affected_windows.join(" / "))+'</div><div class="citation-group"><span class="citation-label">混杂依据</span>'+citationLinks(item.evidence_source_ids,"mechanism")+'</div></div>').join("");
document.getElementById("sources").innerHTML=D.sources.map(source=>'<div class="source"><b>'+esc(source.publisher)+'</b><div class="meta">'+esc(source.evidence_scope)+' · '+esc(source.visibility)+'</div><a href="'+esc(source.url)+'" target="_blank" rel="noopener noreferrer">'+esc(source.source_id)+'</a>'+(source.locator?'<div class="impact">定位：'+esc(source.locator)+'</div>':"")+(source.quote?'<div class="impact">“'+esc(source.quote)+'”</div>':"")+'</div>').join("");
</script>
</body>
</html>
"""


def render_event_page(payload: dict[str, Any]) -> str:
    embedded = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    title = payload["timeline"]["title"]
    heading = f"{payload['timeline']['event_id'].upper()} {title}"
    return (
        EVENT_PAGE_TEMPLATE
        .replace("__PAGE_TITLE__", f"FinGoose {heading}")
        .replace("__EVENT_HEADING__", heading)
        .replace("__DATA__", embedded)
    )


def _source_ids_for_event(
    timeline: dict[str, Any],
    paths: list[dict[str, Any]],
    confounders: dict[str, Any],
) -> set[str]:
    source_ids = {
        source_id
        for node in timeline["nodes"]
        for source_id in node.get("source_ids") or []
    }
    for path in paths:
        source_ids.update(path["event_fact_evidence"])
        source_ids.update(ref["source_id"] for ref in path["mechanism_evidence"])
    for item in confounders["items"]:
        source_ids.update(item["evidence_source_ids"])
    return source_ids

def _validate_storyline(
    event_id: str,
    storyline: dict[str, Any],
    timeline: dict[str, Any],
    paths: list[dict[str, Any]],
    windows: list[dict[str, Any]],
) -> list[str]:
    failures: list[str] = []
    if storyline.get("event_id") != event_id:
        failures.append(f"{event_id}:STORYLINE_EVENT_ID")
    steps = storyline.get("steps") or []
    if not 5 <= len(steps) <= 9:
        failures.append(f"{event_id}:STORYLINE_STEP_COUNT")
    node_by_id = {row.get("fast_node_id"): row for row in timeline.get("nodes") or []}
    valid_path_ids = {row.get("path_id") for row in paths}
    valid_series_ids = {row.get("series_id") for row in windows}
    step_ids = [row.get("story_step_id") for row in steps]
    sequences = [row.get("sequence") for row in steps]
    if len(step_ids) != len(set(step_ids)):
        failures.append(f"{event_id}:DUPLICATE_STORY_STEP_ID")
    if len(sequences) != len(set(sequences)) or sequences != sorted(sequences):
        failures.append(f"{event_id}:INVALID_STORY_SEQUENCE")

    previous_timestamp: float | None = None
    for step in steps:
        step_id = step.get("story_step_id") or f"{event_id}:UNKNOWN_STORY_STEP"
        for field in (
            "title_cn", "narrative_cn", "before_state_cn", "after_state_cn",
            "significance_cn", "evidence_boundary_cn",
        ):
            if not str(step.get(field) or "").strip():
                failures.append(f"{step_id}:MISSING_{field.upper()}")
        status = step.get("evidence_status")
        if status not in {"SUPPORTED", "PARTIALLY_SUPPORTED", "PENDING_EVIDENCE"}:
            failures.append(f"{step_id}:INVALID_STORY_EVIDENCE_STATUS")
        evidence_ids = step.get("evidence_node_ids") or []
        if not evidence_ids:
            failures.append(f"{step_id}:MISSING_EVIDENCE_NODE")
        for node_id in evidence_ids:
            node = node_by_id.get(node_id)
            if not node:
                failures.append(f"{step_id}:UNKNOWN_EVIDENCE_NODE:{node_id}")
            elif node.get("evidence_status") == "PENDING_EVIDENCE" and status != "PENDING_EVIDENCE":
                failures.append(f"{step_id}:PENDING_NODE_PRESENTED_AS_SUPPORTED:{node_id}")
        referenced_paths = {
            path_id
            for field in ("activated_path_ids", "amplified_path_ids", "weakened_path_ids")
            for path_id in step.get(field) or []
        }
        for path_id in sorted(referenced_paths - valid_path_ids):
            failures.append(f"{step_id}:UNKNOWN_PATH:{path_id}")
        for series_id in sorted(set(step.get("market_series_ids") or []) - valid_series_ids):
            failures.append(f"{step_id}:UNKNOWN_MARKET_SERIES:{series_id}")
        precision = step.get("time_precision")
        if precision not in {"TIMESTAMP", "DATE", "RANGE", "UNKNOWN"}:
            failures.append(f"{step_id}:INVALID_TIME_PRECISION")
        if precision == "UNKNOWN" and (step.get("period_start") or step.get("period_end")):
            failures.append(f"{step_id}:UNKNOWN_TIME_WITH_VALUE")
        if precision == "TIMESTAMP":
            timestamp = _timestamp_value(step.get("period_start"))
            if timestamp is None:
                failures.append(f"{step_id}:TIMESTAMP_MISSING")
            elif previous_timestamp is not None and timestamp < previous_timestamp:
                failures.append(f"{step_id}:STORY_TIMESTAMP_INVERSION")
            else:
                previous_timestamp = timestamp
    return failures

def _validate_event(
    event_id: str,
    timeline: dict[str, Any],
    paths: list[dict[str, Any]],
    windows: list[dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    confounders: dict[str, Any],
) -> list[str]:
    failures: list[str] = []

    def validate_source(
        source_id: str,
        context: str,
        *,
        mechanism: bool,
    ) -> dict[str, Any] | None:
        source = sources.get(source_id)
        if not source or not source.get("url"):
            failures.append(f"{context}:UNRESOLVED_SOURCE:{source_id}")
            return None
        if mechanism:
            if source.get("evidence_scope") not in {
                "MECHANISM_PRIOR",
                "POST_EVENT_MECHANISM_CORROBORATION",
            }:
                failures.append(f"{context}:INVALID_MECHANISM_SCOPE:{source_id}")
            if source.get("visibility") not in {
                "PUBLIC_PREDICTION",
                "HIDDEN_FROM_PRIMARY_PREDICTION",
            }:
                failures.append(f"{context}:INVALID_MECHANISM_VISIBILITY:{source_id}")
        else:
            if source.get("event_id") != event_id:
                failures.append(f"{context}:CROSS_EVENT_SOURCE:{source_id}")
            if source.get("evidence_scope") != "EVENT_FACT_AND_TIME":
                failures.append(f"{context}:INVALID_FACT_SCOPE:{source_id}")
        return source

    nodes = timeline.get("nodes") or []
    node_by_id = {node.get("fast_node_id"): node for node in nodes}
    if timeline.get("event_id") != event_id:
        failures.append(f"{event_id}:TIMELINE_EVENT_ID")
    if len(nodes) != 5:
        failures.append(f"{event_id}:NODE_COUNT_NOT_5")
    if sum(node.get("anchor_role") == "PRIMARY" for node in nodes) != 1:
        failures.append(f"{event_id}:PRIMARY_ANCHOR_COUNT")

    for node in nodes:
        node_id = node.get("fast_node_id") or f"{event_id}:UNKNOWN_NODE"
        if node.get("event_id") != event_id:
            failures.append(f"{node_id}:NODE_EVENT_ID")
        status = node.get("evidence_status")
        source_ids = node.get("source_ids") or []
        if status == "VERIFIED_EXISTING":
            if not source_ids:
                failures.append(f"{node_id}:VERIFIED_WITHOUT_SOURCE")
            for source_id in source_ids:
                validate_source(source_id, node_id, mechanism=False)
        elif status == "PENDING_EVIDENCE":
            if source_ids:
                failures.append(f"{node_id}:PENDING_WITH_SOURCE")
            if node.get("promotion_eligible"):
                failures.append(f"{node_id}:PENDING_PROMOTION_ELIGIBLE")
            if node.get("linked_path_ids"):
                failures.append(f"{node_id}:PENDING_WITH_LINKED_PATHS")
        else:
            failures.append(f"{node_id}:INVALID_EVIDENCE_STATUS")

    for path in paths:
        path_id = path.get("path_id") or f"{event_id}:UNKNOWN_PATH"
        if path.get("event_id") != event_id:
            failures.append(f"{path_id}:PATH_EVENT_ID")
        if path.get("selection_status") != "CORE_REVIEWED":
            failures.append(f"{path_id}:SELECTION_STATUS")
        if path.get("confirmation_status") != "PROPOSED":
            failures.append(f"{path_id}:UNAUTHORIZED_CONFIRMATION")
        if path.get("review_basis") != "AI_DESK_REVIEW_NO_HUMAN_CONFIRMATION":
            failures.append(f"{path_id}:REVIEW_BASIS")
        for field in (
            "activation_phases",
            "activation_actions",
            "activation_tags",
            "expected_direction",
            "lag",
            "conditions",
            "invalidation_conditions",
            "counterevidence",
        ):
            if not path.get(field):
                failures.append(f"{path_id}:MISSING_{field.upper()}")

        fact_ids = path.get("event_fact_evidence") or []
        mechanism_refs = path.get("mechanism_evidence") or []
        scoring_eligible = bool(path.get("scoring_eligible"))
        if scoring_eligible and not fact_ids:
            failures.append(f"{path_id}:SCORING_WITHOUT_FACT_EVIDENCE")
        if not mechanism_refs:
            failures.append(f"{path_id}:SCORING_WITHOUT_MECHANISM_EVIDENCE")
        if (
            path.get("anchor_evidence_status") == "PENDING_EVIDENCE"
            and scoring_eligible
        ):
            failures.append(f"{path_id}:PENDING_SCORING_ELIGIBLE")

        anchor_ids = path.get("anchor_fast_node_ids") or []
        if scoring_eligible:
            if len(anchor_ids) != 1:
                failures.append(f"{path_id}:SCORING_ANCHOR_COUNT")
            else:
                anchor = node_by_id.get(anchor_ids[0])
                if (
                    not anchor
                    or anchor.get("evidence_status") != "VERIFIED_EXISTING"
                    or not anchor.get("source_ids")
                ):
                    failures.append(f"{path_id}:SCORING_ANCHOR_NOT_VERIFIED")
                elif not _node_matches_activation(path, anchor):
                    failures.append(f"{path_id}:ANCHOR_SEMANTIC_MISMATCH")
        elif anchor_ids:
            failures.append(f"{path_id}:NONSCORING_WITH_VERIFIED_ANCHOR")

        for source_id in fact_ids:
            validate_source(source_id, path_id, mechanism=False)
        for ref in mechanism_refs:
            source_id = ref.get("source_id")
            source = validate_source(source_id, path_id, mechanism=True)
            if not source:
                continue
            expected_use = (
                "EXCLUDED_TO_PREVENT_LEAKAGE"
                if source.get("visibility") == "HIDDEN_FROM_PRIMARY_PREDICTION"
                else "AVAILABLE_AT_ANCHOR"
            )
            if ref.get("prediction_use") != expected_use:
                failures.append(f"{path_id}:MECHANISM_VISIBILITY:{source_id}")
            if ref.get("evidence_scope") != source.get("evidence_scope"):
                failures.append(f"{path_id}:MECHANISM_SCOPE_MISMATCH:{source_id}")

    core_rows = [row for row in windows if row.get("asset_tier") == "CORE"]
    expected_core_ids = set(EVENT_CONFIGS[event_id]["core_series_ids"])
    actual_core_ids = [row.get("series_id") for row in core_rows]
    all_series_ids = [row.get("series_id") for row in windows]
    if len(all_series_ids) != len(set(all_series_ids)):
        failures.append(f"{event_id}:DUPLICATE_SERIES")
    if set(actual_core_ids) != expected_core_ids:
        failures.append(f"{event_id}:CORE_ASSET_SET")
    if len(core_rows) != 4:
        failures.append(f"{event_id}:CORE_ASSET_COUNT_NOT_4")

    for row in windows:
        series_id = row.get("series_id") or "UNKNOWN_SERIES"
        context = f"{event_id}:{series_id}"
        if row.get("event_id") != event_id:
            failures.append(f"{context}:MARKET_EVENT_ID")
        if not row.get("timezone"):
            failures.append(f"{context}:MISSING_TIMEZONE")
        if not row.get("calendar_id"):
            failures.append(f"{context}:MISSING_CALENDAR")
        if row.get("daily_t0_rule") != "T0_CLOSE_EQUALS_D1":
            failures.append(f"{context}:DAILY_T0_RULE")
        formulas = row.get("formulas") or {}
        for formula_name in (
            "raw_change",
            "standardized_change",
            "relative_change",
        ):
            if not formulas.get(formula_name):
                failures.append(f"{context}:MISSING_FORMULA:{formula_name}")
        display_windows = row.get("display_windows") or {}
        if list(display_windows) != WINDOW_LABELS:
            failures.append(f"{context}:WINDOW_KEYS")
        t0 = display_windows.get("T0") or {}
        d1 = display_windows.get("D1") or {}
        if t0.get("date") != d1.get("date") or t0.get("value") != d1.get("value"):
            failures.append(f"{context}:T0_D1_MISMATCH")
        for label, point in display_windows.items():
            if point.get("value") is not None and not point.get("date"):
                failures.append(f"{context}:{label}:VALUE_WITHOUT_DATE")

    if confounders.get("event_id") != event_id:
        failures.append(f"{event_id}:CONFOUNDER_EVENT_ID")
    item_windows: set[str] = set()
    valid_path_ids = {path.get("path_id") for path in paths}
    for item in confounders.get("items") or []:
        item_id = item.get("confounder_id") or f"{event_id}:UNKNOWN_CONFOUNDER"
        affected_windows = set(item.get("affected_windows") or [])
        item_windows.update(affected_windows)
        if not affected_windows:
            failures.append(f"{item_id}:MISSING_AFFECTED_WINDOWS")
        if not set(item.get("affected_path_ids") or []).issubset(valid_path_ids):
            failures.append(f"{item_id}:UNKNOWN_AFFECTED_PATH")
        evidence_ids = item.get("evidence_source_ids") or []
        if not evidence_ids:
            failures.append(f"{item_id}:MISSING_EVIDENCE")
        for source_id in evidence_ids:
            validate_source(source_id, item_id, mechanism=True)

    for horizon, level in (confounders.get("by_horizon") or {}).items():
        if level in {"MATERIAL", "DOMINANT", "UNRESOLVED"} and horizon not in item_windows:
            failures.append(f"{event_id}:CONFOUNDER_WINDOW_UNSUPPORTED:{horizon}")
    return failures

def render_overview(rows: list[dict[str, Any]]) -> str:
    totals = {
        "events": len(rows),
        "nodes": sum(row["verified_nodes"] + row["pending_nodes"] for row in rows),
        "pending": sum(row["pending_nodes"] for row in rows),
        "paths": sum(row["core_paths"] for row in rows),
        "core_assets": sum(row["core_assets"] for row in rows),
        "extension_assets": sum(row["extension_assets"] for row in rows),
    }
    cards = "".join(
        '<a class="event" href="events/{0}/index.html">'
        '<div><span>{1}</span><h2>{2}</h2></div>'
        '<div class="metrics">'
        '<span><b>{3}/5</b> 已验证</span>'
        '<span><b>{4}</b> 待补证</span>'
        '<span><b>{5}</b> 核心路径</span>'
        '<span><b>{6}</b> 核心资产</span>'
        '<span><b>{7}</b> 扩展资产</span>'
        '</div><div class="state">{8}<br>验证状态：{9}</div></a>'.format(
            row["event_id"],
            row["event_id"].upper(),
            row["title"],
            row["verified_nodes"],
            row["pending_nodes"],
            row["core_paths"],
            row["core_assets"],
            row["extension_assets"],
            row["decision"],
            row["validation_status"],
        )
        for row in rows
    )
    summary = (
        f'<div class="summary"><span><b>{totals["events"]}</b> 事件</span>'
        f'<span><b>{totals["nodes"]}</b> 节点</span>'
        f'<span><b>{totals["pending"]}</b> 待补证节点</span>'
        f'<span><b>{totals["paths"]}</b> 核心候选路径</span>'
        f'<span><b>{totals["core_assets"]}</b> 核心市场序列</span>'
        f'<span><b>{totals["extension_assets"]}</b> 扩展资产</span></div>'
    )
    return """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FinGoose 十事件快速候选集</title><style>
:root{--ink:#172027;--muted:#65727b;--line:#d8dee2;--paper:#f5f7f6;--red:#b83d36}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:"Microsoft YaHei",Arial,sans-serif;letter-spacing:0}header{background:#182229;color:#fff;border-bottom:4px solid var(--red);padding:18px 24px}h1{font-size:24px;margin:5px 0}.wrap{max-width:1180px;margin:auto;padding:18px}.summary{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:12px;font-size:13px}.summary b{font-size:20px}.event{display:grid;grid-template-columns:minmax(260px,1fr) minmax(430px,1.4fr) 150px;gap:16px;align-items:center;background:#fff;border-top:1px solid var(--line);padding:12px 14px;text-decoration:none;color:inherit}.event:first-child{border-top:3px solid var(--red)}.event:hover{background:#f9fbfb}.event span{font-size:11px;color:var(--muted)}.event h2{font-size:15px;margin:3px 0}.metrics{font-size:12px;color:var(--muted);display:flex;gap:9px;align-items:center;flex-wrap:wrap}.metrics b{color:var(--ink)}.state{font-size:11px;text-align:right;color:#82540d;line-height:1.5}@media(max-width:720px){header{padding:14px}.wrap{padding:10px}.event{grid-template-columns:1fr}.metrics{flex-wrap:wrap}.state{text-align:left}}
</style></head><body><header><small>FinGoose / MACRO EVENT ATTRIBUTION</small><h1>十事件时间线与动态传导链</h1><div>RAPID_CANDIDATE · formal_ready=false · SHA / 历史分位延后</div></header><main class="wrap">""" + summary + cards + "</main></body></html>"

EVENT_OUTPUT_FILES = {
    "timeline.json",
    "event_storyline.json",
    "core_transmission_paths.json",
    "market_windows.jsonl",
    "confounders.json",
    "stage_edge_market_map.json",
    "sources.json",
    "validation_report.json",
    "index.html",
}


def _validate_output_tree(output: Path) -> list[str]:
    failures: list[str] = []
    events_root = output / "events"
    expected_event_ids = set(EVENT_CONFIGS)
    if not events_root.is_dir():
        return [f"{output}:MISSING_EVENTS_DIR"]

    actual_event_ids = {
        path.name
        for path in events_root.iterdir()
        if path.is_dir()
    }
    for event_id in sorted(actual_event_ids - expected_event_ids):
        failures.append(f"UNEXPECTED_EVENT_DIR:{event_id}")
    for event_id in sorted(expected_event_ids - actual_event_ids):
        failures.append(f"MISSING_EVENT_DIR:{event_id}")

    for event_id in sorted(expected_event_ids & actual_event_ids):
        event_root = events_root / event_id
        actual_files = {
            path.name
            for path in event_root.iterdir()
            if path.is_file()
        }
        for name in sorted(actual_files - EVENT_OUTPUT_FILES):
            failures.append(f"UNEXPECTED_EVENT_FILE:{event_id}:{name}")
        for name in sorted(EVENT_OUTPUT_FILES - actual_files):
            failures.append(f"MISSING_EVENT_FILE:{event_id}:{name}")
        if any(path.is_dir() for path in event_root.iterdir()):
            failures.append(f"UNEXPECTED_EVENT_SUBDIRECTORY:{event_id}")
    return failures


def build(root: Path, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    sources = build_source_registry(root)
    timelines = build_timelines(root)
    paths_by_event = build_core_paths(root, sources)
    markets = build_market_packages(root)
    confounders = build_confounders()
    mappings = build_stage_mappings(timelines)
    storylines = build_storylines(timelines, paths_by_event, markets)
    hard_failures: list[str] = []
    overview_rows: list[dict[str, Any]] = []
    payloads: dict[str, dict[str, Any]] = {}

    for event_id in EVENT_CONFIGS:
        event_root = output / "events" / event_id
        event_root.mkdir(parents=True, exist_ok=True)
        timeline = timelines[event_id]
        paths = paths_by_event[event_id]
        windows = markets[event_id]
        confounder = confounders[event_id]
        storyline = storylines[event_id]
        mapping = mappings[event_id]
        relevant_ids = _source_ids_for_event(timeline, paths, confounder)
        event_sources = [
            sources[source_id]
            for source_id in sorted(relevant_ids)
            if source_id in sources
        ]
        event_failures = _validate_event(
            event_id, timeline, paths, windows, sources, confounder
        )
        event_failures.extend(
            _validate_storyline(event_id, storyline, timeline, paths, windows)
        )
        hard_failures.extend(event_failures)
        event_report = {
            "event_id": event_id,
            "release_tier": RELEASE_TIER,
            "formal_ready": False,
            "sha_gate": "DEFERRED_BY_USER_FOR_RAPID_CANDIDATE",
            "hard_failures": event_failures,
            "chronology_status": timeline["chronology_status"],
            "chronology_warnings": timeline["chronology_warnings"],
        }
        payload = {
            "timeline": timeline,
            "storyline": storyline,
            "paths": paths,
            "windows": windows,
            "confounders": confounder,
            "mapping": mapping,
            "sources": event_sources,
            "validation": event_report,
        }
        payloads[event_id] = payload
        write_json(event_root / "timeline.json", timeline)
        write_json(event_root / "event_storyline.json", storyline)
        write_json(
            event_root / "core_transmission_paths.json",
            {
                "event_id": event_id,
                "release_tier": RELEASE_TIER,
                "paths": paths,
            },
        )
        write_jsonl(event_root / "market_windows.jsonl", windows)
        write_json(event_root / "confounders.json", confounder)
        write_json(event_root / "stage_edge_market_map.json", mapping)
        write_json(event_root / "sources.json", event_sources)
        write_json(event_root / "validation_report.json", event_report)
        (event_root / "index.html").write_text(
            render_event_page(payload),
            encoding="utf-8",
        )
        overview_rows.append({
            "event_id": event_id,
            "title": timeline["title"],
            "verified_nodes": sum(
                node["evidence_status"] == "VERIFIED_EXISTING"
                for node in timeline["nodes"]
            ),
            "pending_nodes": sum(
                node["evidence_status"] == "PENDING_EVIDENCE"
                for node in timeline["nodes"]
            ),
            "core_paths": len(paths),
            "core_assets": len(
                [row for row in windows if row["asset_tier"] == "CORE"]
            ),
            "extension_assets": len(
                [row for row in windows if row["asset_tier"] != "CORE"]
            ),
            "decision": confounder["clean_attribution_decision"],
            "validation_status": "PASS" if not event_failures else "FAIL",
        })


    for event_id in EVENT_CONFIGS:
        event_root = output / "events" / event_id
        (event_root / "index.html").write_text(
            render_workbench(payloads, event_id),
            encoding="utf-8",
        )
    hard_failures.extend(_validate_output_tree(output))

    chronology_warnings = [
        {"event_id": event_id, **warning}
        for event_id, timeline in timelines.items()
        for warning in timeline["chronology_warnings"]
    ]


    report = {
        "dataset_version": DATASET_VERSION,
        "release_tier": RELEASE_TIER,
        "formal_ready": False,
        "production_dataset_modified": False,
        "sha_gate": "DEFERRED_BY_USER_FOR_RAPID_CANDIDATE",
        "percentile_gate": "DEFERRED_VALIDATION",
        "event_count": len(timelines),
        "timeline_node_count": sum(
            len(row["nodes"]) for row in timelines.values()
        ),
        "storyline_step_count": sum(
            len(row["steps"]) for row in storylines.values()
        ),
        "pending_storyline_step_count": sum(
            step["evidence_status"] == "PENDING_EVIDENCE"
            for row in storylines.values()
            for step in row["steps"]
        ),
        "verified_node_count": sum(
            node["evidence_status"] == "VERIFIED_EXISTING"
            for row in timelines.values()
            for node in row["nodes"]
        ),
        "pending_evidence_count": sum(
            node["evidence_status"] == "PENDING_EVIDENCE"
            for row in timelines.values()
            for node in row["nodes"]
        ),
        "core_path_count": sum(len(rows) for rows in paths_by_event.values()),
        "chronology_warning_count": len(chronology_warnings),
        "chronology_warnings": chronology_warnings,
        "confirmed_path_count": 0,
        "core_market_series_count": sum(
            row["asset_tier"] == "CORE"
            for rows in markets.values()
            for row in rows
        ),
        "extension_market_series_count": sum(
            row["asset_tier"] != "CORE"
            for rows in markets.values()
            for row in rows
        ),
        "hard_failures": hard_failures,
        "warnings": [
            "Eight input-derived nodes remain PENDING_EVIDENCE.",
            "All 35 core paths remain PROPOSED and are not human-confirmed.",
            "T0 and D1 are aliases for the same daily close.",
            "D3/D5/D20 are challenge or window-dependent where confounders overlap.",
            "SHA and empirical-percentile gates are deferred by user for this rapid candidate.",
            "Three curated-sequence timestamp inversions are explicitly reported.",
        ],
    }
    (output / "index.html").write_text(
        render_workbench(payloads, "event-01"),
        encoding="utf-8",
    )
    write_json(output / "validation_report.json", report)
    write_json(
        output / "manifest.json",
        {
            "dataset_version": DATASET_VERSION,
            "release_tier": RELEASE_TIER,
            "formal_ready": False,
            "counts": {
                "events": report["event_count"],
                "timeline_nodes": report["timeline_node_count"],
                "core_paths": report["core_path_count"],
                "core_market_series": report["core_market_series_count"],
                "extension_market_series": report["extension_market_series_count"],
            },
            "sha_gate": report["sha_gate"],
        },
    )
    readme = (
        "# FinGoose Ten-Event Rapid Candidate v2\n\n"
        "10 events, 50 timeline nodes, 35 core candidate paths, "
        "40 core market packages and one event-02 extension.\n\n"
        "Eight input-derived nodes remain PENDING_EVIDENCE. "
        "formal_ready=false; confirmed_path_count=0. "
        "Long-tail edge review, SHA and empirical-percentile gates are deferred.\n"
    )
    (output / "README.md").write_text(readme, encoding="utf-8")
    return report


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    output = root / "work" / "ten_event_rapid_candidate_v2"
    report = build(root, output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["hard_failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
