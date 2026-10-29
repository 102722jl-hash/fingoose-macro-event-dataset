from __future__ import annotations

import argparse
import csv
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

from fingoose_macro_event_attribution_v2 import compute_enhanced_market_window


EVENT_ID = "event-02"
DATASET_VERSION = "fingoose-event-02-rapid-candidate-v2.0"
RELEASE_TIER = "RAPID_CANDIDATE"
GENERATED_AT = "2026-07-31T00:00:00+08:00"
PRIMARY_ANCHOR = "fast-event-02-M03"

SERIES_META = {
    "DCOILBRENTEU": {
        "name": "Brent 原油现货价",
        "unit": "美元/桶",
        "role": "能源供应风险",
        "metric_type": "price_return_pct",
        "benchmark": "DCOILWTICO",
    },
    "DHHNGSP": {
        "name": "Henry Hub 天然气现货价",
        "unit": "美元/百万英热单位",
        "role": "天然气供应风险代理",
        "metric_type": "price_return_pct",
        "benchmark": "DCOILBRENTEU",
    },
    "DGS10": {
        "name": "美国 10 年期国债收益率",
        "unit": "%",
        "role": "通胀与避险共同作用的利率代理",
        "metric_type": "yield_basis_points",
        "benchmark": None,
    },
    "VIXCLS": {
        "name": "VIX 收盘指数",
        "unit": "指数点",
        "role": "风险规避",
        "metric_type": "price_return_pct",
        "benchmark": None,
    },
    "SP500": {
        "name": "标普 500 指数",
        "unit": "指数点",
        "role": "风险资产",
        "metric_type": "price_return_pct",
        "benchmark": None,
    },
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _read_market_csv(path: Path, series_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                value = float(row[series_id])
            except (KeyError, TypeError, ValueError):
                continue
            rows.append({"date": row["observation_date"], "value": value})
    return rows


def _point(point: dict[str, Any], *, alias: str | None = None) -> dict[str, Any]:
    result = {
        "date": point["date"],
        "value": point["value"],
        "raw_change": point.get("raw_change"),
        "standardized_change": point.get("standardized_change"),
        "relative_change": point.get("relative_change"),
        "empirical_percentile": point.get("empirical_percentile"),
    }
    if alias:
        result["observation_alias"] = alias
    return result


def _formulas(metric_type: str, benchmark: str | None) -> dict[str, str]:
    raw = (
        "(V_h - V_T-1) / abs(V_T-1) * 100%"
        if metric_type != "yield_basis_points"
        else "(V_h - V_T-1) * 100 basis points"
    )
    return {
        "raw_change": raw,
        "standardized_change": (
            "raw_change / (stddev(previous 60 session daily changes) "
            "* sqrt(session_distance))"
        ),
        "relative_change": (
            f"raw_change - {benchmark} raw_change on the same dates"
            if benchmark
            else "null: no ex-ante comparable benchmark was assigned"
        ),
        "empirical_percentile": (
            "rank of raw_change among pre-event placebo windows with equal session length"
        ),
    }


def _rapid_market_row(
    series_id: str,
    computed: dict[str, Any],
    *,
    source_path: str,
) -> dict[str, Any]:
    meta = SERIES_META[series_id]
    windows = computed["windows"]
    d1 = windows["D1"]
    display_windows = {
        "T-1": _point(windows["T1"]),
        "T0": _point(d1, alias="D1_CLOSE"),
        "D1": _point(d1, alias="T0_CLOSE"),
        "D3": _point(windows["D3"]),
        "D5": _point(windows["D5"]),
        "D20": _point(windows["D20"]),
    }
    return {
        "event_id": EVENT_ID,
        "anchor_fast_node_id": PRIMARY_ANCHOR,
        "series_id": series_id,
        "series_name": meta["name"],
        "unit": meta["unit"],
        "asset_role": meta["role"],
        "metric_type": meta["metric_type"],
        "benchmark_series_id": meta["benchmark"],
        "timezone": "UTC",
        "calendar_id": f"FRED-{series_id}",
        "observation_cutoff": "21:00:00",
        "t0": {
            "date": computed["t0_session"],
            "alignment_reason": "IN_SESSION",
            "anchor_at": "2022-02-24T05:00:00+00:00",
        },
        "daily_t0_rule": "T0_CLOSE_EQUALS_D1",
        "daily_resolution_note": (
            "日频序列只有 2022-02-24 收盘观测，因此 T0 与 D1 共用同一绝对值；"
            "不得将其解释为两个独立观测。"
        ),
        "estimation": computed["estimation"],
        "display_windows": display_windows,
        "formulas": _formulas(meta["metric_type"], meta["benchmark"]),
        "observation_source": {
            "path": source_path,
            "provider": "Federal Reserve Economic Data (FRED)",
            "sha_gate": "DEFERRED_BY_USER_FOR_RAPID_CANDIDATE",
        },
        "confounder_by_horizon": {
            "T0": "MINOR",
            "D1": "MINOR",
            "D3": "MATERIAL",
            "D5": "MATERIAL",
            "D20": "DOMINANT",
        },
    }


def _build_market_windows(root: Path) -> list[dict[str, Any]]:
    market_root = root / "evidence_snapshots" / "macro_event_attribution_v1" / "market" / "fred"
    production = {
        row["series_id"]: row
        for row in _read_jsonl(
            root / "data" / "market_event_attribution_v2_candidate" / "market_windows.jsonl"
        )
        if row["event_id"] == EVENT_ID
    }
    observations = {
        series_id: _read_market_csv(market_root / f"{series_id}.csv", series_id)
        for series_id in {"DCOILBRENTEU", "DCOILWTICO", "DHHNGSP", "DGS10"}
    }
    computed_by_series: dict[str, dict[str, Any]] = {}
    for series_id in ("DCOILBRENTEU", "VIXCLS", "SP500"):
        row = production[series_id]
        computed_by_series[series_id] = {
            "metric_type": row["metric_type"],
            "baseline": row["baseline"],
            "t0_session": row["t0"]["date"],
            "estimation": row["estimation"],
            "windows": row["windows"],
        }
    computed_by_series["DHHNGSP"] = compute_enhanced_market_window(
        observations=observations["DHHNGSP"],
        t0_session="2022-02-24",
        metric_type="price_return_pct",
        benchmark_observations=observations["DCOILBRENTEU"],
        benchmark_metric_type="price_return_pct",
    )
    computed_by_series["DGS10"] = compute_enhanced_market_window(
        observations=observations["DGS10"],
        t0_session="2022-02-24",
        metric_type="yield_basis_points",
    )
    return [
        _rapid_market_row(
            series_id,
            computed_by_series[series_id],
            source_path=f"evidence_snapshots/macro_event_attribution_v1/market/fred/{series_id}.csv",
        )
        for series_id in ("DCOILBRENTEU", "DHHNGSP", "DGS10", "VIXCLS", "SP500")
    ]


def _sources() -> list[dict[str, Any]]:
    return [
        {
            "source_id": "supplemental-fast-event-02-M02",
            "publisher": "President of Russia",
            "source_tier": "A",
            "url": "http://en.kremlin.ru/events/president/news/67843",
            "evidence_scope": "EVENT_FACT_AND_TIME",
            "visibility": "PUBLIC_PREDICTION",
        },
        {
            "source_id": "event02-nato-statement",
            "publisher": "NATO",
            "source_tier": "B",
            "url": "https://www.nato.int/en/about-us/official-texts-and-resources/official-texts/2022/02/24/statement-by-the-north-atlantic-council-on-russias-attack-on-ukraine",
            "evidence_scope": "EVENT_FACT_AND_TIME",
            "visibility": "PUBLIC_PREDICTION",
        },
        {
            "source_id": "supplemental-fast-event-02-M05",
            "publisher": "U.S. Department of the Treasury",
            "source_tier": "A",
            "url": "https://home.treasury.gov/news/press-releases/jy1138",
            "evidence_scope": "EVENT_FACT_AND_TIME",
            "visibility": "POST_PRIMARY_WINDOW",
        },
        {
            "source_id": "mechanism-imf-2022-03-15",
            "publisher": "International Monetary Fund",
            "source_tier": "A",
            "url": "https://www.imf.org/en/Blogs/Articles/2022/03/15/blog-how-war-in-ukraine-is-reverberating-across-worlds-regions-031522",
            "published_at": "2022-03-15",
            "evidence_scope": "POST_EVENT_MECHANISM_CORROBORATION",
            "visibility": "HIDDEN_FROM_PRIMARY_PREDICTION",
            "locator": "Paragraph beginning 'Beyond the suffering and humanitarian crisis'",
            "quote": "Impacts will flow through three main channels. One, higher prices for commodities like food and energy will push up inflation further...",
        },
        {
            "source_id": "mechanism-ecb-eb-2022-04",
            "publisher": "European Central Bank",
            "source_tier": "A",
            "url": "https://www.ecb.europa.eu/press/economic-bulletin/focus/2022/html/ecb.ebbox202204_01~68ef3c3dc6.en.html",
            "published_at": "2022-06",
            "evidence_scope": "POST_EVENT_MECHANISM_CORROBORATION",
            "visibility": "HIDDEN_FROM_PRIMARY_PREDICTION",
            "locator": "Box: The impact of the war in Ukraine on euro area energy markets",
            "quote": "The war in Ukraine has generated a sharp increase in energy prices and significant volatility in energy markets.",
        },
        {
            "source_id": "mechanism-fed-2022-05-27",
            "publisher": "Board of Governors of the Federal Reserve System",
            "source_tier": "A",
            "url": "https://www.federalreserve.gov/econres/notes/feds-notes/the-effect-of-the-war-in-ukraine-on-global-activity-and-inflation-20220527.html",
            "published_at": "2022-05-27",
            "evidence_scope": "POST_EVENT_MECHANISM_CORROBORATION",
            "visibility": "HIDDEN_FROM_PRIMARY_PREDICTION",
            "locator": "Opening summary and model-results section",
            "quote": "Commodity markets are in turmoil and financial markets have been highly volatile since the start of the conflict.",
        },
        {
            "source_id": "mechanism-stlouisfed-2022-q4",
            "publisher": "Federal Reserve Bank of St. Louis",
            "source_tier": "A",
            "url": "https://www.stlouisfed.org/publications/review/2022/10/21/financial-market-reactions-to-the-russian-invasion-of-ukraine",
            "published_at": "2022-10-21",
            "evidence_scope": "POST_EVENT_MECHANISM_CORROBORATION",
            "visibility": "HIDDEN_FROM_PRIMARY_PREDICTION",
            "locator": "Introduction",
            "quote": "The global price of oil rose by about 35 percent from February 21, 2022, to March 8, 2022.",
        },
    ]


def _mechanism_ref(source_id: str) -> dict[str, str]:
    return {
        "source_id": source_id,
        "evidence_scope": "POST_EVENT_MECHANISM_CORROBORATION",
        "prediction_use": "EXCLUDED_TO_PREVENT_LEAKAGE",
    }


def _core_paths() -> dict[str, Any]:
    common = {
        "selection_status": "CORE_REVIEWED",
        "confirmation_status": "PROPOSED",
        "review_basis": "AI_DESK_REVIEW_NO_HUMAN_CONFIRMATION",
    }
    paths = [
        {
            **common,
            "path_id": "event-02-P01-energy-supply",
            "name": "冲突升级 → 能源供应风险 → 原油与天然气",
            "anchor_fast_node_ids": ["fast-event-02-M02", "fast-event-02-M03", "fast-event-02-M04"],
            "chain": ["GEOPOLITICAL_CONFLICT", "ENERGY_SUPPLY", "PHYSICAL_SUPPLY_RISK", "DCOILBRENTEU|DHHNGSP"],
            "asset_series_ids": ["DCOILBRENTEU", "DHHNGSP"],
            "expected_direction": {"IMMEDIATE": "UP", "SHORT_TERM": "UP", "MEDIUM_TERM": "MIXED"},
            "lag": {"minimum": "P0D", "maximum": "P20D"},
            "conditions": ["俄罗斯能源供应中断概率上升", "替代供应短期不足", "需求预期未快速坍塌"],
            "invalidation_conditions": ["能源出口保持完全可用", "替代供应或需求下修压过供应风险"],
            "event_fact_evidence": ["supplemental-fast-event-02-M02", "event02-nato-statement"],
            "mechanism_evidence": [_mechanism_ref("mechanism-ecb-eb-2022-04"), _mechanism_ref("mechanism-imf-2022-03-15")],
            "counterevidence": ["能源价格和供应紧张在入侵前已存在，不能把全部涨幅归因于单一节点。"],
        },
        {
            **common,
            "path_id": "event-02-P02-inflation-rates",
            "name": "能源冲击 → 通胀预期 → 利率重新定价",
            "anchor_fast_node_ids": ["fast-event-02-M03", "fast-event-02-M04"],
            "chain": ["ENERGY_PRICE_SHOCK", "INFLATION_EXPECTATIONS", "POLICY_RATE_EXPECTATIONS", "DGS10"],
            "asset_series_ids": ["DGS10"],
            "expected_direction": {"IMMEDIATE": "MIXED", "SHORT_TERM": "UP", "MEDIUM_TERM": "UP"},
            "lag": {"minimum": "P0D", "maximum": "P20D"},
            "conditions": ["能源涨价被认为具有持续性", "央行反应函数重视通胀失锚风险"],
            "invalidation_conditions": ["避险买盘压低长端收益率", "增长冲击压过通胀渠道", "政策指引转鸽"],
            "event_fact_evidence": ["event02-nato-statement"],
            "mechanism_evidence": [_mechanism_ref("mechanism-imf-2022-03-15"), _mechanism_ref("mechanism-fed-2022-05-27")],
            "counterevidence": ["DGS10 不是纯通胀预期序列，同时承载实际利率与避险需求，因此只作为扩展代理。"],
        },
        {
            **common,
            "path_id": "event-02-P03-risk-appetite",
            "name": "尾部风险上升 → 风险规避 → VIX 与股票",
            "anchor_fast_node_ids": ["fast-event-02-M03", "fast-event-02-M04"],
            "chain": ["GEOPOLITICAL_TAIL_RISK", "RISK_APPETITE", "VOLATILITY_AND_EQUITY_REPRICING", "VIXCLS|SP500"],
            "asset_series_ids": ["VIXCLS", "SP500"],
            "expected_direction": {"IMMEDIATE": "VIX_UP__SP500_DOWN", "SHORT_TERM": "VIX_UP__SP500_DOWN", "MEDIUM_TERM": "MIXED"},
            "lag": {"minimum": "P0D", "maximum": "P5D"},
            "conditions": ["冲突范围与制裁后果仍不确定", "风险资产尚未完全计价"],
            "invalidation_conditions": ["冲突迅速受控", "政策宽松预期或超预期盈利主导市场"],
            "event_fact_evidence": ["event02-nato-statement"],
            "mechanism_evidence": [_mechanism_ref("mechanism-fed-2022-05-27"), _mechanism_ref("mechanism-stlouisfed-2022-q4")],
            "counterevidence": ["2022-02-24 美股收盘反弹且 VIX 低于前一日，说明日内反转和美联储路径重估可压过初始风险规避。"],
        },
        {
            **common,
            "path_id": "event-02-P04-sanctions-trade",
            "name": "制裁与价格上限 → 能源贸易摩擦 → 供给与收入双目标",
            "anchor_fast_node_ids": ["fast-event-02-M05"],
            "chain": ["PRICE_CAP_POLICY", "ENERGY_TRADE_FRICTION", "SUPPLY_CONTINUITY_VS_REVENUE_RESTRICTION", "DCOILBRENTEU"],
            "asset_series_ids": ["DCOILBRENTEU"],
            "expected_direction": {"IMMEDIATE": "MIXED", "SHORT_TERM": "MIXED", "MEDIUM_TERM": "MIXED"},
            "lag": {"minimum": "P0D", "maximum": "P20D"},
            "conditions": ["价格上限执行具有约束力", "俄罗斯供应反应与第三方规避行为可观测"],
            "invalidation_conditions": ["上限缺乏执行力", "全球需求或 OPEC+ 供给成为主导因素"],
            "event_fact_evidence": ["supplemental-fast-event-02-M05"],
            "mechanism_evidence": [_mechanism_ref("mechanism-imf-2022-03-15"), _mechanism_ref("mechanism-ecb-eb-2022-04")],
            "counterevidence": ["该政策同时追求限制俄方收入与维持全球供应，方向不能预设为单边上涨或下跌。"],
        },
    ]
    return {
        "event_id": EVENT_ID,
        "release_tier": RELEASE_TIER,
        "confirmation_policy": "Only human-reviewed edges may later become CONFIRMED.",
        "paths": paths,
    }


def _timeline(root: Path) -> dict[str, Any]:
    nodes = [
        deepcopy(row)
        for row in _read_jsonl(root / "work" / "timeline_fast_candidate_v2" / "timeline_nodes.jsonl")
        if row["event_id"] == EVENT_ID
    ]
    impacts = {
        "fast-event-02-M01": ([], "背景敏感度候选；证据未闭环，不激活可评分传导边。", "NOT_COMPUTED"),
        "fast-event-02-M02": (["event-02-P01-energy-supply", "event-02-P03-risk-appetite"], "冲突正式启动，强化供应中断与尾部风险。", "PRIMARY_ANCHOR_SHARED_DAY"),
        "fast-event-02-M03": (["event-02-P01-energy-supply", "event-02-P02-inflation-rates", "event-02-P03-risk-appetite"], "公开主锚点，启动核心冲击观测窗口。", "PRIMARY_ANCHOR"),
        "fast-event-02-M04": (["event-02-P02-inflation-rates", "event-02-P03-risk-appetite"], "同日政策响应强化安全与风险偏好分支。", "SAME_DAY_UNRESOLVED"),
        "fast-event-02-M05": (["event-02-P04-sanctions-trade"], "价格上限开启新的政策与贸易摩擦分支。", "OUTSIDE_PRIMARY_ANCHOR_WINDOW"),
    }
    for node in nodes:
        linked, summary, scope = impacts[node["fast_node_id"]]
        node["linked_path_ids"] = linked
        node["impact_summary"] = summary
        node["market_observation_scope"] = scope
    return {
        "event_id": EVENT_ID,
        "title": "俄罗斯对乌克兰发动全面进攻及后续能源制裁",
        "release_tier": RELEASE_TIER,
        "formal_ready": False,
        "primary_anchor_fast_node_id": PRIMARY_ANCHOR,
        "nodes": nodes,
        "daily_resolution": {
            "status": "SAME_DAY_UNRESOLVED",
            "date": "2022-02-24",
            "node_ids": ["fast-event-02-M03", "fast-event-02-M04"],
            "reason": "两个节点的公开时间相同，日频收盘值无法识别各自的边际影响。",
        },
    }


def _confounders() -> dict[str, Any]:
    return {
        "event_id": EVENT_ID,
        "clean_attribution_decision": "CHALLENGE_ONLY",
        "reason": "只有 D1 可作为较窄事件窗口观察；D3 以后制裁、政策预期与持续战争共同作用。",
        "by_horizon": {"T0": "MINOR", "D1": "MINOR", "D3": "MATERIAL", "D5": "MATERIAL", "D20": "DOMINANT"},
        "items": [
            {
                "confounder_id": "event-02-C01-preexisting-energy-tightness",
                "level": "MATERIAL",
                "active_from": "2021-01-01",
                "description": "疫情后需求恢复、投资偏弱与库存偏紧已在入侵前推高能源价格。",
                "affected_paths": ["event-02-P01-energy-supply", "event-02-P02-inflation-rates"],
                "evidence_source_ids": ["mechanism-ecb-eb-2022-04", "mechanism-imf-2022-03-15"],
            },
            {
                "confounder_id": "event-02-C02-policy-repricing",
                "level": "MATERIAL",
                "active_from": "2022-01-01",
                "description": "高通胀与美联储紧缩路径重估同时影响股票、VIX 与长端收益率。",
                "affected_paths": ["event-02-P02-inflation-rates", "event-02-P03-risk-appetite"],
                "evidence_source_ids": ["mechanism-fed-2022-05-27"],
            },
            {
                "confounder_id": "event-02-C03-sanctions-sequence",
                "level": "MATERIAL",
                "active_from": "2022-02-26",
                "description": "后续金融制裁与能源限制在 D3/D5 窗口内形成独立冲击。",
                "affected_paths": ["event-02-P01-energy-supply", "event-02-P03-risk-appetite", "event-02-P04-sanctions-trade"],
                "evidence_source_ids": ["mechanism-stlouisfed-2022-q4"],
            },
            {
                "confounder_id": "event-02-C04-ongoing-war-and-policy",
                "level": "DOMINANT",
                "active_from": "2022-03-01",
                "description": "D20 包含持续战事、更多制裁、OPEC+ 供给决策与 3 月 FOMC，不能作为单节点干净归因。",
                "affected_paths": ["event-02-P01-energy-supply", "event-02-P02-inflation-rates", "event-02-P03-risk-appetite"],
                "evidence_source_ids": ["mechanism-fed-2022-05-27", "mechanism-ecb-eb-2022-04"],
            },
        ],
    }


def _stage_mapping(timeline: dict[str, Any]) -> dict[str, Any]:
    status_map = {
        "fast-event-02-M01": "NOT_COMPUTED",
        "fast-event-02-M02": "PRIMARY_ANCHOR_SHARED_DAY",
        "fast-event-02-M03": "PRIMARY_ANCHOR",
        "fast-event-02-M04": "SAME_DAY_UNRESOLVED",
        "fast-event-02-M05": "OUTSIDE_PRIMARY_ANCHOR_WINDOW",
    }
    return {
        "event_id": EVENT_ID,
        "mapping_rule": "node -> activated/modified core paths -> preselected market series",
        "node_mappings": [
            {
                "fast_node_id": node["fast_node_id"],
                "phase": node["phase"],
                "node_action": node["node_action"],
                "path_ids": node["linked_path_ids"],
                "series_ids": sorted({
                    series
                    for path_id in node["linked_path_ids"]
                    for series in {
                        "event-02-P01-energy-supply": ["DCOILBRENTEU", "DHHNGSP"],
                        "event-02-P02-inflation-rates": ["DGS10"],
                        "event-02-P03-risk-appetite": ["VIXCLS", "SP500"],
                        "event-02-P04-sanctions-trade": ["DCOILBRENTEU"],
                    }[path_id]
                }),
                "market_window_status": status_map[node["fast_node_id"]],
            }
            for node in timeline["nodes"]
        ],
    }


def _validate(
    timeline: dict[str, Any],
    paths: dict[str, Any],
    windows: list[dict[str, Any]],
    mapping: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    if len(timeline["nodes"]) != 5:
        failures.append("EVENT02_NODE_COUNT_NOT_5")
    if timeline["nodes"][0]["evidence_status"] != "PENDING_EVIDENCE":
        failures.append("M01_PENDING_BOUNDARY_BROKEN")
    if len(paths["paths"]) != 4:
        failures.append("CORE_PATH_COUNT_NOT_4")
    if any(path["confirmation_status"] != "PROPOSED" for path in paths["paths"]):
        failures.append("UNAUTHORIZED_CONFIRMED_PATH")
    if {row["series_id"] for row in windows} != set(SERIES_META):
        failures.append("MARKET_SERIES_SET_MISMATCH")
    required = ["T-1", "T0", "D1", "D3", "D5", "D20"]
    for row in windows:
        if list(row["display_windows"]) != required:
            failures.append(f"WINDOW_LABEL_MISMATCH:{row['series_id']}")
        if row["display_windows"]["T-1"]["value"] is None:
            failures.append(f"MISSING_BASELINE_VALUE:{row['series_id']}")
    if len(mapping["node_mappings"]) != 5:
        failures.append("STAGE_MAPPING_COUNT_NOT_5")
    return failures


def _html(data: dict[str, Any]) -> str:
    embedded = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FinGoose Event-02 Rapid Candidate</title>
<style>
:root{{--ink:#182028;--muted:#64707a;--line:#d8dee3;--paper:#f7f8f6;--panel:#fff;--red:#b83b35;--green:#18745b;--amber:#a76712;--blue:#286b8e;}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);font-family:"Microsoft YaHei",Arial,sans-serif;letter-spacing:0}}
header{{background:#172129;color:#fff;padding:20px 28px;border-bottom:4px solid #d34b40}} header small{{color:#aeb9c1}} h1{{font-size:24px;margin:6px 0 4px}} h2{{font-size:18px;margin:0 0 14px}} h3{{font-size:15px;margin:0 0 8px}}
.wrap{{max-width:1320px;margin:auto;padding:22px}} .status{{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}} .badge{{border:1px solid #56636d;padding:5px 8px;font-size:12px}} .warn{{color:#ffd18a}}
.tabs{{display:flex;gap:2px;border-bottom:1px solid var(--line);margin-bottom:18px}} .tabs button{{border:0;background:transparent;padding:11px 14px;font-weight:700;cursor:pointer}} .tabs button.active{{border-bottom:3px solid var(--red);color:var(--red)}}
.view{{display:none}} .view.active{{display:block}} .grid{{display:grid;grid-template-columns:minmax(320px,1fr) minmax(420px,1.7fr);gap:18px}} .panel{{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:16px}}
.timeline{{border-left:2px solid #8e9aa3;margin-left:8px;padding-left:20px}} .node{{position:relative;padding:0 0 22px}} .node:before{{content:"";position:absolute;width:10px;height:10px;border-radius:50%;background:var(--blue);left:-26px;top:5px}} .node.pending:before{{background:var(--amber)}} .meta{{font-size:12px;color:var(--muted);margin-bottom:5px}} .fact{{line-height:1.55}} .impact{{margin-top:7px;color:#34434e;font-size:13px}}
.path{{border-top:1px solid var(--line);padding:14px 0}} .path:first-child{{border-top:0;padding-top:0}} .chain{{font-family:Consolas,monospace;font-size:13px;color:#234d63;overflow-wrap:anywhere}} .directions{{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}} .directions span{{font-size:12px;border:1px solid var(--line);padding:4px 6px}}
.citation-group{{margin-top:9px;display:flex;gap:6px;align-items:center;flex-wrap:wrap}} .citation-label{{font-size:12px;font-weight:700;color:#46545e}}
.citation-link{{display:inline-flex;max-width:100%;padding:4px 7px;border:1px solid #b8c6cf;border-radius:4px;background:#f5fafc;color:#175d83;font-size:12px;line-height:1.35;text-decoration:none;overflow-wrap:anywhere}} .citation-link.mechanism{{border-color:#d2c2a5;background:#fffaf0;color:#725019}}
.citation-empty{{font-size:12px;color:var(--muted);font-style:italic}}
select{{padding:8px;border:1px solid #aab4bb;background:#fff;max-width:100%}} table{{width:100%;border-collapse:collapse;font-size:13px;margin-top:12px}} th,td{{padding:9px 8px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}} th:first-child,td:first-child{{text-align:left}} .scroll{{overflow-x:auto}}
.note{{border-left:3px solid var(--amber);background:#fff8e9;padding:10px 12px;margin:12px 0;font-size:13px;line-height:1.5}} .source{{border-top:1px solid var(--line);padding:12px 0}} a{{color:#175d83}} .kpi{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:0 0 18px}} .kpi div{{background:#fff;border:1px solid var(--line);padding:12px}} .kpi b{{font-size:22px;display:block}}
@media(max-width:760px){{header{{padding:16px}}.wrap{{padding:12px}}.grid{{grid-template-columns:1fr}}.kpi{{grid-template-columns:repeat(2,1fr)}}.tabs{{overflow-x:auto}}.tabs button{{white-space:nowrap}}}}
</style>
</head>
<body>
<header><small>FinGoose / MACRO EVENT ATTRIBUTION</small><h1>EVENT-02 俄罗斯对乌克兰发动全面进攻</h1><div class="status"><span class="badge">RAPID_CANDIDATE</span><span class="badge">formal_ready=false</span><span class="badge warn">M01 PENDING_EVIDENCE</span></div></header>
<main class="wrap">
<div class="kpi"><div><b>5</b>时间线节点</div><div><b>4</b>核心传导路径</div><div><b>5</b>市场序列</div><div><b>0</b>已确认传导边</div></div>
<nav class="tabs"><button class="active" data-view="timeline">事件时间线</button><button data-view="paths">动态传导链</button><button data-view="market">绝对值与变化</button><button data-view="evidence">混杂与竞争解释</button></nav>
<section id="timeline" class="view active"><div class="grid"><div class="panel"><h2>证据时间线</h2><div id="timeline-list" class="timeline"></div></div><div class="panel"><h2>阶段联动</h2><div class="note"><b>SAME_DAY_UNRESOLVED</b><br>M03 与 M04 同为 2022-02-24 05:00Z，日频数据不能拆分两者影响。</div><div id="mapping"></div></div></div></section>
<section id="paths" class="view"><div class="panel"><h2>动态传导链</h2><div class="note">CORE_REVIEWED 表示已筛为核心候选，不代表人工确认；所有路径仍为 PROPOSED。</div><div id="path-list"></div></div></section>
<section id="market" class="view"><div class="panel"><h2>核心资产窗口</h2><select id="series"></select><div class="note"><b>T0_CLOSE_EQUALS_D1</b><br>日频数据的 T0 与 D1 均指事件当日收盘，只是一条观测的两个阅读标签。</div><div class="scroll"><table><thead><tr><th>窗口</th><th>日期</th><th>绝对值</th><th>原始变化</th><th>标准化</th><th>相对变化</th><th>历史分位</th></tr></thead><tbody id="market-body"></tbody></table></div><div id="formula" class="note"></div></div></section>
<section id="evidence" class="view"><div class="grid"><div class="panel"><h2>混杂与竞争解释</h2><div class="note">结论：CHALLENGE_ONLY。D3 后不进入干净归因主分数。</div><div id="confounders"></div></div><div class="panel"><h2>证据来源</h2><div id="sources"></div></div></div></section>
</main>
<script id="data" type="application/json">{embedded}</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent); const esc=s=>String(s??'UNKNOWN').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
const sourceById=Object.fromEntries(D.sources.map(s=>[s.source_id,s]));
function citationLinks(refs,role){{
  const ids=(refs||[]).map(ref=>typeof ref==='string'?ref:ref.source_id);
  if(!ids.length)return '<span class="citation-empty">\u6682\u65e0\u5df2\u9a8c\u8bc1\u5f15\u7528</span>';
  return ids.map(id=>{{
    const source=sourceById[id];
    if(!source||!source.url)return '<span class="citation-empty">UNKNOWN &middot; '+esc(id)+'</span>';
    const postEvent=source.visibility==='HIDDEN_FROM_PRIMARY_PREDICTION';
    const roleLabel=postEvent?'\u4e8b\u540e\u673a\u5236\u9a8c\u8bc1':(role==='mechanism'?'\u673a\u5236':'\u4e8b\u5b9e\u4e0e\u65f6\u95f4');
    return '<a class="citation-link '+role+'" href="'+esc(source.url)+'" target="_blank" rel="noopener noreferrer">&nearr; '+esc(source.publisher)+' &middot; '+roleLabel+'</a>';
  }}).join('');
}}
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{{document.querySelectorAll('.tabs button,.view').forEach(x=>x.classList.remove('active'));b.classList.add('active');document.getElementById(b.dataset.view).classList.add('active')}});
document.getElementById('mapping').innerHTML=D.mapping.node_mappings.map(m=>`<div class="source"><b>${{esc(m.fast_node_id)}} · ${{esc(m.market_window_status)}}</b><div class="meta">${{esc(m.path_ids.join(' · ')||'无激活路径')}}</div><div>${{esc(m.series_ids.join(' / ')||'无市场窗口')}}</div></div>`).join('');
document.getElementById('timeline-list').innerHTML=D.timeline.nodes.map(n=>`<article class="node ${{n.evidence_status==='PENDING_EVIDENCE'?'pending':''}}"><div class="meta">${{esc(n.fast_node_id)}} &middot; ${{esc(n.phase)}} &middot; ${{esc(n.occurred_at)}}</div><h3>${{esc(n.node_action)}} / ${{esc(n.evidence_status)}}</h3><div class="fact">${{esc(n.fact)}}</div><div class="impact">${{esc(n.impact_summary)}}</div><div class="citation-group"><span class="citation-label">\u4e8b\u5b9e\u6765\u6e90</span>${{citationLinks(n.source_ids,'fact')}}</div></article>`).join('');
document.getElementById('path-list').innerHTML=D.paths.paths.map(p=>`<article class="path"><h3>${{esc(p.name)}}</h3><div class="chain">${{esc(p.chain.join(' \u2192 '))}}</div><div class="directions">${{Object.entries(p.expected_direction).map(([k,v])=>`<span>${{esc(k)}}: ${{esc(v)}}</span>`).join('')}}</div><div class="meta">\u6761\u4ef6\uff1a${{esc(p.conditions.join('\uff1b'))}}</div><div class="meta">\u5931\u6548\uff1a${{esc(p.invalidation_conditions.join('\uff1b'))}}</div><div class="impact">\u53cd\u8bc1\uff1a${{esc(p.counterevidence.join('\uff1b'))}}</div><div class="citation-group"><span class="citation-label">\u4e8b\u4ef6\u4e8b\u5b9e\u4f9d\u636e</span>${{citationLinks(p.event_fact_evidence,'fact')}}</div><div class="citation-group"><span class="citation-label">\u673a\u5236\u4f9d\u636e</span>${{citationLinks(p.mechanism_evidence,'mechanism')}}</div></article>`).join('');
const sel=document.getElementById('series'); sel.innerHTML=D.windows.map(w=>`<option value="${{esc(w.series_id)}}">${{esc(w.series_name)}} · ${{esc(w.series_id)}}</option>`).join('');
const fmt=v=>v==null?'UNKNOWN':Number(v).toLocaleString('zh-CN',{{maximumFractionDigits:4}}); function renderMarket(){{const w=D.windows.find(x=>x.series_id===sel.value)||D.windows[0];document.getElementById('market-body').innerHTML=Object.entries(w.display_windows).map(([k,p])=>`<tr><td>${{k}}</td><td>${{esc(p?.date)}}</td><td>${{fmt(p?.value)}} ${{esc(w.unit)}}</td><td>${{fmt(p?.raw_change)}}</td><td>${{fmt(p?.standardized_change)}}</td><td>${{fmt(p?.relative_change)}}</td><td>${{p?.empirical_percentile==null?'UNKNOWN':fmt(p.empirical_percentile*100)+'%'}}</td></tr>`).join('');document.getElementById('formula').innerHTML='<b>计算公式</b><br>'+esc(w.formulas.raw_change)+'<br>'+esc(w.formulas.standardized_change)+'<br>'+esc(w.formulas.relative_change)}} sel.onchange=renderMarket;renderMarket();
document.getElementById('confounders').innerHTML=D.confounders.items.map(c=>`<div class="source"><b>${{esc(c.level)}} · ${{esc(c.confounder_id)}}</b><div>${{esc(c.description)}}</div></div>`).join('');
document.getElementById('sources').innerHTML=D.sources.map(s=>`<div class="source"><b>${{esc(s.publisher)}}</b><div class="meta">${{esc(s.evidence_scope)}} · ${{esc(s.visibility)}}</div><a href="${{esc(s.url)}}" target="_blank" rel="noopener noreferrer">${{esc(s.source_id)}}</a>${{s.quote?`<div class="impact">“${{esc(s.quote)}}”</div>`:''}}</div>`).join('');
</script></body></html>"""


def build(root: Path, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    timeline = _timeline(root)
    paths = _core_paths()
    windows = _build_market_windows(root)
    confounders = _confounders()
    mapping = _stage_mapping(timeline)
    sources = _sources()
    failures = _validate(timeline, paths, windows, mapping)
    report = {
        "dataset_version": DATASET_VERSION,
        "release_tier": RELEASE_TIER,
        "formal_ready": False,
        "production_dataset_modified": False,
        "sha_gate": "DEFERRED_BY_USER_FOR_RAPID_CANDIDATE",
        "event_count": 1,
        "timeline_node_count": len(timeline["nodes"]),
        "verified_node_count": sum(n["evidence_status"] == "VERIFIED_EXISTING" for n in timeline["nodes"]),
        "pending_evidence_count": sum(n["evidence_status"] == "PENDING_EVIDENCE" for n in timeline["nodes"]),
        "core_path_count": len(paths["paths"]),
        "confirmed_path_count": 0,
        "market_series_count": len(windows),
        "hard_failures": failures,
        "warnings": [
            "fast-event-02-M01 remains PENDING_EVIDENCE and does not activate scored edges.",
            "M03 and M04 are SAME_DAY_UNRESOLVED at daily frequency.",
            "T0 and D1 are aliases of the same daily close, not independent observations.",
            "DGS10 is an expanded rate proxy, not a pure inflation-expectations measure.",
            "Mechanism sources published after the primary window are excluded from prediction-visible evidence.",
            "D3/D5/D20 are challenge-only because material or dominant confounders overlap.",
        ],
    }
    manifest = {
        "dataset_version": DATASET_VERSION,
        "release_tier": RELEASE_TIER,
        "formal_ready": False,
        "generated_at": GENERATED_AT,
        "scope": "event-02-only",
        "files": [
            "timeline.json", "core_transmission_paths.json", "market_windows.jsonl",
            "confounders.json", "stage_edge_market_map.json", "sources.json",
            "validation_report.json", "README.md", "index.html",
        ],
        "counts": {
            "timeline_nodes": len(timeline["nodes"]),
            "core_paths": len(paths["paths"]),
            "market_series": len(windows),
            "sources": len(sources),
        },
        "hashes": "DEFERRED_BY_USER",
    }

    _write_json(output / "timeline.json", timeline)
    _write_json(output / "core_transmission_paths.json", paths)
    _write_jsonl(output / "market_windows.jsonl", windows)
    _write_json(output / "confounders.json", confounders)
    _write_json(output / "stage_edge_market_map.json", mapping)
    _write_json(output / "sources.json", sources)
    _write_json(output / "validation_report.json", report)
    _write_json(output / "manifest.json", manifest)
    page_data = {"timeline": timeline, "paths": paths, "windows": windows, "confounders": confounders, "mapping": mapping, "sources": sources}
    (output / "index.html").write_text(_html(page_data), encoding="utf-8")
    (output / "README.md").write_text(
        """# FinGoose event-02 RAPID_CANDIDATE

release_tier=RAPID_CANDIDATE  
formal_ready=false  
production_dataset_modified=false  
sha_gate=DEFERRED_BY_USER_FOR_RAPID_CANDIDATE

本目录是 event-02 独立试点，不覆盖生产 v2。交付含 5 节点证据时间线、4 条核心候选传导路径、5 个市场序列的 T-1/T0/D1/D3/D5/D20 绝对值与派生变化、混杂登记及阶段联动页面。

关键边界：M01 保持 PENDING_EVIDENCE；M03/M04 为 SAME_DAY_UNRESOLVED；所有传导路径仍为 PROPOSED；D3 以后仅进入挑战集；T0 与 D1 是同一日频收盘观测。
""",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or args.root / "work" / "event_02_rapid_candidate_v2"
    report = build(args.root.resolve(), output.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
