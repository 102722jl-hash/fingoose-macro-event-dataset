import argparse
import copy
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.io_utils import read_jsonl, write_jsonl


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_ROOT.parents[1]
REQUIRED_OFFSETS = {
    "T_MINUS_20": -20,
    "T_MINUS_1": -1,
    "T0": 0,
    "D1": 1,
    "D3": 3,
    "D5": 5,
    "D20": 20,
}
CONFOUNDING_ORDER = {"CLEAN": 0, "MINOR": 1, "MATERIAL": 2, "DOMINANT": 3, "UNRESOLVED": 4}
MYSQL_MARKET_AUDIT_SQL = (
    "SELECT TABLE_NAME FROM information_schema.tables WHERE table_schema=DATABASE() "
    "AND (LOWER(TABLE_NAME) REGEXP 'eod|index|sw|price|daily|quote') ORDER BY TABLE_NAME"
)
EXPECTED_MYSQL_DATABASE = "workspace"
SW1_CODES = {
    "交通运输": "801170",
    "医药生物": "801150",
    "家用电器": "801110",
    "房地产": "801180",
    "电力设备": "801730",
    "电子": "801080",
    "石油石化": "801960",
}


def _parse_snapshot_bars(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("data", {}).get("klines") or []
    bars: list[dict[str, Any]] = []
    for raw in rows:
        fields = raw.split(",")
        if len(fields) < 3:
            raise ValueError(f"invalid kline in {path.name}")
        bars.append({"date": fields[0], "close": float(fields[2])})
    if not bars:
        raise ValueError(f"no kline observations in {path.name}")
    return bars


def _industry_classification(industry: str) -> dict[str, Any]:
    sw1_id = SW1_CODES.get(industry, "UNKNOWN")
    return {
        "system": "SHENWAN",
        "sw1_id": sw1_id,
        "sw1_name": industry,
        "sw2_id": "UNKNOWN",
        "sw2_name": "UNKNOWN",
        "historical_effective_date_status": "NEEDS_HUMAN_REVIEW",
        "classification_status": (
            "CANDIDATE_SW1_MAPPING" if sw1_id != "UNKNOWN" else "NEEDS_HUMAN_REVIEW"
        ),
    }


def _project_industry_impacts(
    candidates: list[dict[str, Any]],
    anchors: list[dict[str, Any]],
    bindings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    anchors_by_id = {row["anchor_id"]: row for row in anchors}
    anchors_by_id.update(
        {
            row["superseded_anchor_id"]: row
            for row in anchors
            if row.get("superseded_anchor_id")
        }
    )
    bindings_by_anchor_edge = {
        (f"anchor-{row['anchor_fast_node_id']}", row["edge_id"]): row for row in bindings
    }
    projected: list[dict[str, Any]] = []
    for source in candidates:
        row = copy.deepcopy(source)
        anchor = anchors_by_id.get(row["anchor_id"])
        if anchor is None:
            raise ValueError(f"industry anchor missing from reviewed catalog: {row['anchor_id']}")
        linked = []
        for edge in row.get("transmission_edges", []):
            binding = bindings_by_anchor_edge.get((row["anchor_id"], edge["edge_id"]))
            if binding is not None:
                linked.append(binding)
        node_ids = {
            value
            for binding in linked
            for value in (binding["from_node_id"], binding["to_node_id"])
        }
        direction = row.get("expected_industry_direction")
        if direction not in {"UP", "DOWN", "MIXED"}:
            direction = "UNKNOWN"
        row.update(
            {
                "dataset_version": "fingoose-verifiable-evaluation-phase1-v2-candidate",
                "event_node_id": anchor["fast_node_id"],
                "anchor_id": anchor["anchor_id"],
                "binding_ids": sorted({item["binding_id"] for item in linked}),
                "channel_node_ids": sorted(item for item in node_ids if "-channel-" in item),
                "intermediate_variable_node_ids": sorted(
                    item for item in node_ids if "-intermediate-" in item
                ),
                "direction_path": {
                    "IMMEDIATE": direction,
                    "SHORT_TERM": direction,
                    "MEDIUM_TERM": "UNKNOWN",
                },
                "direction_status": (
                    "AI_REVIEWED" if direction != "UNKNOWN" and linked else "NEEDS_HUMAN_REVIEW"
                ),
                "industry_classification": _industry_classification(row.get("industry", "UNKNOWN")),
                "lineage_status": (
                    "GRAPH_LINKED_CANDIDATE"
                    if linked
                    and any("-channel-" in item for item in node_ids)
                    and any("-intermediate-" in item for item in node_ids)
                    else "UNLINKED_CANDIDATE"
                ),
                "verified_company_link_count": 0,
                "review": {
                    "reviewer_type": "AI_DESK_REVIEW",
                    "reviewed_at": "2026-08-01T12:30:00+08:00",
                    "rationale_zh": (
                        "行业方向缺少独立机制证据，保持未知并等待人工审核；未使用事后价格回填。"
                        if direction == "UNKNOWN"
                        else "行业方向沿用事前机制候选并关联到已审核绑定；未使用事后价格选方向。"
                    ),
                },
                "causal_attribution_allowed": bool(
                    anchor["causal_attribution_allowed"]
                    and any(
                        item["binding_status"] == "AI_REVIEWED" for item in linked
                    )
                ),
                "post_event_price_used_for_direction": False,
                "formal_ready": False,
            }
        )
        projected.append(row)
    return projected


def _load_confounding(confounder_root: Path, event_id: str) -> dict[str, str]:
    path = confounder_root / event_id / "confounders.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("by_horizon", {})


def _build_company_window(
    source: dict[str, Any], snapshot_root: Path, confounder_root: Path
) -> dict[str, Any]:
    bars = _parse_snapshot_bars(snapshot_root / source["snapshot_path"])
    by_date = {bar["date"]: index for index, bar in enumerate(bars)}
    t0_date = source["observations"]["T0"]["date"]
    if t0_date not in by_date:
        raise ValueError(f"T0 observation absent from snapshot: {source['price_window_id']}")
    t0_index = by_date[t0_date]
    selected: dict[str, dict[str, Any]] = {}
    for name, offset in REQUIRED_OFFSETS.items():
        index = t0_index + offset
        if index < 0 or index >= len(bars):
            raise ValueError(f"insufficient bars for {name}: {source['price_window_id']}")
        selected[name] = {
            "date": bars[index]["date"],
            "close": bars[index]["close"],
            "trading_session_offset": offset,
            "status": "OBSERVED",
        }
    baseline = selected["T_MINUS_1"]["close"]
    for observation in selected.values():
        observation.update(
            {
                "absolute_return": observation["close"] / baseline - 1.0,
                "broad_market_relative_return": None,
                "industry_relative_return": None,
                "broad_market_benchmark_status": "UNAVAILABLE",
                "industry_benchmark_status": "UNAVAILABLE",
            }
        )

    confounding = _load_confounding(confounder_root, source["event_id"])
    confounding_by_horizon = {
        "T_MINUS_20": "UNRESOLVED",
        "T_MINUS_1": "CLEAN",
        "T0": confounding.get("T0", "UNRESOLVED"),
        "D1": confounding.get("D1", "UNRESOLVED"),
        "D3": confounding.get("D3", "UNRESOLVED"),
        "D5": confounding.get("D5", "UNRESOLVED"),
        "D20": confounding.get("D20", "UNRESOLVED"),
    }
    grade = max(confounding_by_horizon.values(), key=lambda item: CONFOUNDING_ORDER[item])
    result = copy.deepcopy(source)
    result.update(
        {
            "dataset_version": "fingoose-verifiable-evaluation-phase1-v2-candidate",
            "observations": selected,
            "calendar_alignment": "EXCHANGE_TRADING_SESSIONS",
            "suspension_alignment": "UNVERIFIED",
            "session_alignment_note": (
                "Observations are indexed by vendor bars. Exchange calendar and suspension data "
                "were not available, so holidays, suspensions, and missing bars are not distinguished."
            ),
            "confounding_by_horizon": confounding_by_horizon,
            "confounding_grade": grade,
            "broad_market_benchmark": {
                "status": "UNAVAILABLE",
                "reason": "No A-share broad-market daily table was found in the approved read-only database scope.",
            },
            "industry_benchmark": {
                "status": "UNAVAILABLE",
                "reason": "No event-date Shenwan index history was found in the approved read-only database scope.",
            },
            "formulas": {
                "absolute_return": "company_close_h / company_close_T_MINUS_1 - 1",
                "broad_market_relative_return": "company_return - broad_market_return",
                "industry_relative_return": "company_return - industry_return",
            },
            "licence": {
                "scope": "UNKNOWN",
                "use": "CANDIDATE_RESEARCH_ONLY",
                "retrieved_at": None,
                "redistribution_allowed": False,
            },
            "redistribution_allowed": False,
            "formal_ready": False,
        }
    )
    return result


def _exposure_gaps(windows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "gap_id": f"exposure-gap-{row['event_id']}-{row['company_code'].lower().replace('.', '-')}",
            "event_id": row["event_id"],
            "company_code": row["company_code"],
            "company_name": row["company_name"],
            "status": "OPEN",
            "official_company_exposure_verified": False,
            "required_evidence": [
                "事件前已公开年报或公告中的业务暴露",
                "地区或产品收入暴露",
                "收入、成本或资产负债表敏感性",
            ],
            "review_status": "NEEDS_HUMAN_REVIEW",
        }
        for row in windows
    ]


def build_market_layers(
    industry_candidates: list[dict[str, Any]],
    reviewed_anchors: list[dict[str, Any]],
    reviewed_bindings: list[dict[str, Any]],
    company_windows: list[dict[str, Any]],
    snapshot_root: Path,
    confounder_root: Path,
    mysql_audit: dict[str, Any],
) -> dict[str, Any]:
    impacts = _project_industry_impacts(
        industry_candidates, reviewed_anchors, reviewed_bindings
    )
    windows = [
        _build_company_window(row, snapshot_root, confounder_root) for row in company_windows
    ]
    query_manifest = [copy.deepcopy(mysql_audit)]
    candidate_mentions = sum(len(row["companies"]) for row in impacts)
    graph_linked_mentions = sum(
        len(row["companies"])
        for row in impacts
        if row["lineage_status"] == "GRAPH_LINKED_CANDIDATE"
    )
    verified_links = sum(row["verified_company_link_count"] for row in impacts)
    return {
        "industry_impacts": impacts,
        "company_windows": windows,
        "company_exposure_gaps": _exposure_gaps(windows),
        "mysql_query_manifest": query_manifest,
        "reviewed_anchors": reviewed_anchors,
        "reviewed_bindings": reviewed_bindings,
        "candidate_company_mention_count": candidate_mentions,
        "graph_linked_company_mention_count": graph_linked_mentions,
        "verified_company_link_count": verified_links,
    }


def market_hard_failures(result: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    impacts = result.get("industry_impacts", [])
    windows = result.get("company_windows", [])
    gaps = result.get("company_exposure_gaps", [])
    queries = result.get("mysql_query_manifest", [])
    reviewed_anchors = result.get("reviewed_anchors", [])
    reviewed_bindings = result.get("reviewed_bindings", [])
    anchors_by_id = {row.get("anchor_id"): row for row in reviewed_anchors}
    anchors_by_id.update(
        {
            row.get("superseded_anchor_id"): row
            for row in reviewed_anchors
            if row.get("superseded_anchor_id")
        }
    )
    bindings_by_id = {row.get("binding_id"): row for row in reviewed_bindings}

    candidate_mentions = sum(len(row.get("companies", [])) for row in impacts)
    graph_linked_mentions = sum(
        len(row.get("companies", []))
        for row in impacts
        if row.get("lineage_status") == "GRAPH_LINKED_CANDIDATE"
    )
    verified_links = sum(row.get("verified_company_link_count", 0) for row in impacts)
    if len(impacts) != 43:
        failures.append("INDUSTRY_IMPACT_COUNT_MISMATCH")
    if candidate_mentions != 72 or result.get("candidate_company_mention_count") != candidate_mentions:
        failures.append("CANDIDATE_COMPANY_MENTION_COUNT_MISMATCH")
    if graph_linked_mentions != 33 or result.get("graph_linked_company_mention_count") != graph_linked_mentions:
        failures.append("GRAPH_LINKED_COMPANY_MENTION_COUNT_MISMATCH")
    if result.get("verified_company_link_count") != verified_links:
        failures.append("VERIFIED_COMPANY_LINK_COUNT_MISMATCH")
    if verified_links != 0:
        failures.append("UNSUPPORTED_VERIFIED_COMPANY_LINK")
    if any(row.get("post_event_price_used_for_direction") is not False for row in impacts):
        failures.append("HINDSIGHT_DIRECTION_SELECTION")
    if any(
        row.get("causal_attribution_allowed")
        and row.get("direction_status") != "AI_REVIEWED"
        for row in impacts
    ):
        failures.append("UNREVIEWED_INDUSTRY_CAUSAL_ATTRIBUTION")

    for row in impacts:
        binding_ids = row.get("binding_ids", [])
        if row.get("lineage_status") == "GRAPH_LINKED_CANDIDATE":
            linked = [bindings_by_id.get(binding_id) for binding_id in binding_ids]
            anchor = anchors_by_id.get(row.get("anchor_id"))
            if (
                not binding_ids
                or not row.get("channel_node_ids")
                or not row.get("intermediate_variable_node_ids")
                or any(binding is None for binding in linked)
                or any(binding.get("event_id") != row.get("event_id") for binding in linked)
                or anchor is None
                or anchor.get("event_id") != row.get("event_id")
                or anchor.get("fast_node_id") != row.get("event_node_id")
                or any(
                    binding.get("anchor_fast_node_id") != anchor.get("fast_node_id")
                    for binding in linked
                )
            ):
                failures.append("BROKEN_GRAPH_LINKED_LINEAGE")
                continue
            node_ids = {
                node_id
                for binding in linked
                for node_id in (binding.get("from_node_id"), binding.get("to_node_id"))
            }
            expected_channels = {node_id for node_id in node_ids if "-channel-" in node_id}
            expected_intermediates = {
                node_id for node_id in node_ids if "-intermediate-" in node_id
            }
            if (
                set(row.get("channel_node_ids", [])) != expected_channels
                or set(row.get("intermediate_variable_node_ids", [])) != expected_intermediates
            ):
                failures.append("BROKEN_GRAPH_LINKED_LINEAGE")
        elif binding_ids:
            failures.append("UNLINKED_INDUSTRY_HAS_BINDINGS")

    if len(windows) != 30:
        failures.append("COMPANY_WINDOW_COUNT_MISMATCH")
    if len({row.get("price_window_id") for row in windows}) != len(windows):
        failures.append("DUPLICATE_COMPANY_WINDOW_ID")
    required = set(REQUIRED_OFFSETS)
    for row in windows:
        observations = row.get("observations", {})
        if set(observations) != required:
            failures.append("MISSING_REQUIRED_MARKET_OBSERVATION")
            continue
        baseline = observations["T_MINUS_1"].get("close")
        if not isinstance(baseline, (int, float)) or baseline == 0:
            failures.append("INVALID_MARKET_BASELINE")
            continue
        for observation in observations.values():
            close = observation.get("close")
            absolute_return = observation.get("absolute_return")
            if not isinstance(close, (int, float)) or not isinstance(absolute_return, (int, float)):
                failures.append("NON_RECOMPUTABLE_COMPANY_RETURN")
                continue
            if abs((close / baseline - 1.0) - absolute_return) > 1e-12:
                failures.append("NON_RECOMPUTABLE_COMPANY_RETURN")
            for relative_field, benchmark_field in (
                ("broad_market_relative_return", "broad_market_return"),
                ("industry_relative_return", "industry_return"),
            ):
                relative_value = observation.get(relative_field)
                benchmark_value = observation.get(benchmark_field)
                if relative_value is not None and not isinstance(benchmark_value, (int, float)):
                    failures.append("NON_RECOMPUTABLE_RELATIVE_RETURN")
                elif relative_value is not None and abs(
                    (absolute_return - benchmark_value) - relative_value
                ) > 1e-12:
                    failures.append("NON_RECOMPUTABLE_RELATIVE_RETURN")

    if len(gaps) != len(windows):
        failures.append("COMPANY_EXPOSURE_GAP_COUNT_MISMATCH")
    if any(
        row.get("status") != "OPEN"
        or row.get("official_company_exposure_verified") is not False
        for row in gaps
    ):
        failures.append("COMPANY_EXPOSURE_GAP_STATE_INVALID")

    required_query_fields = {
        "query_id",
        "query_type",
        "execution_status",
        "executed_at",
        "database",
        "table",
        "sql",
        "parameters",
        "selected_fields",
        "time_range",
        "row_count",
        "matched_tables",
        "result_sha256",
        "exit_code",
        "a_share_price_table_found",
        "broad_market_index_table_found",
        "shenwan_index_table_found",
        "credentials_included",
        "execution_authenticity_status",
    }
    if len(queries) != 1:
        failures.append("MYSQL_AUDIT_COUNT_MISMATCH")
    else:
        query = queries[0]
        matched_tables = query.get("matched_tables")
        expected_hash = None
        if isinstance(matched_tables, list) and all(
            isinstance(item, str) for item in matched_tables
        ):
            expected_hash = hashlib.sha256(
                chr(10).join(matched_tables).encode("utf-8")
            ).hexdigest()
        try:
            executed_at = datetime.fromisoformat(
                str(query.get("executed_at", "")).replace("Z", "+00:00")
            )
        except ValueError:
            executed_at = None
        names = [item.casefold() for item in matched_tables or [] if isinstance(item, str)]
        expected_a_share = any(
            re.search(r"(?:a[_-]?share|ashare|stock|equity)", name)
            for name in names
        )
        expected_broad_market = any(
            re.search(r"(?:index|csi[_-]?300|hs[_-]?300|000300)", name)
            for name in names
        )
        expected_shenwan = any(
            re.search(r"(?:shenwan|sw[_-]?[12]|swindex)", name)
            for name in names
        )
        if (
            not required_query_fields <= set(query)
            or query.get("query_id") != "mysql-market-availability-audit-2026-08-01"
            or query.get("query_type") != "READ_ONLY_METADATA_AUDIT"
            or query.get("execution_status") != "EXECUTED"
            or executed_at is None
            or executed_at.tzinfo is None
            or executed_at > datetime.now(executed_at.tzinfo) + timedelta(minutes=5)
            or query.get("database") != EXPECTED_MYSQL_DATABASE
            or query.get("table") != "information_schema.tables"
            or query.get("sql") != MYSQL_MARKET_AUDIT_SQL
            or query.get("parameters") != {}
            or query.get("selected_fields") != ["TABLE_NAME"]
            or query.get("time_range") is not None
            or query.get("credentials_included") is not False
            or query.get("execution_authenticity_status")
            != "UNVERIFIED_NO_SIGNED_EXECUTION_LOG"
            or query.get("exit_code") != 0
            or not isinstance(matched_tables, list)
            or query.get("row_count") != len(matched_tables)
            or matched_tables != sorted(matched_tables)
            or query.get("result_sha256") != expected_hash
            or query.get("a_share_price_table_found") is not expected_a_share
            or query.get("broad_market_index_table_found") is not expected_broad_market
            or query.get("shenwan_index_table_found") is not expected_shenwan
        ):
            failures.append("MYSQL_AUDIT_INVALID")
    return sorted(set(failures))


def _build_outputs() -> dict[str, Any]:
    result = build_market_layers(
        industry_candidates=read_jsonl(
            PROJECT_ROOT
            / "work"
            / "event_industry_impact_v1_candidate"
            / "event_industry_impact_candidates.jsonl"
        ),
        reviewed_anchors=read_jsonl(PACKAGE_ROOT / "anchor_catalog.jsonl"),
        reviewed_bindings=read_jsonl(PACKAGE_ROOT / "dynamic_edge_bindings.jsonl"),
        company_windows=read_jsonl(
            PROJECT_ROOT
            / "work"
            / "company_price_windows_public_vendor_v1_candidate"
            / "company_price_windows.jsonl"
        ),
        snapshot_root=(
            PROJECT_ROOT / "work" / "company_price_windows_public_vendor_v1_candidate"
        ),
        confounder_root=PROJECT_ROOT / "work" / "ten_event_rapid_candidate_v2" / "events",
        mysql_audit=json.loads(
            (PACKAGE_ROOT / "config" / "mysql_market_availability_audit.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    write_jsonl(PACKAGE_ROOT / "event_industry_impacts.jsonl", result["industry_impacts"])
    write_jsonl(PACKAGE_ROOT / "company_price_windows.jsonl", result["company_windows"])
    write_jsonl(PACKAGE_ROOT / "company_exposure_gaps.jsonl", result["company_exposure_gaps"])
    write_jsonl(PACKAGE_ROOT / "mysql_query_manifest.jsonl", result["mysql_query_manifest"])
    report = {
        "industry_impact_count": len(result["industry_impacts"]),
        "candidate_company_mention_count": result["candidate_company_mention_count"],
        "graph_linked_company_mention_count": result["graph_linked_company_mention_count"],
        "verified_company_link_count": result["verified_company_link_count"],
        "industry_direction_human_review_count": sum(
            row["direction_status"] == "NEEDS_HUMAN_REVIEW"
            for row in result["industry_impacts"]
        ),
        "company_window_count": len(result["company_windows"]),
        "company_exposure_gap_count": len(result["company_exposure_gaps"]),
        "broad_market_benchmark_unavailable_count": sum(
            row["broad_market_benchmark"]["status"] == "UNAVAILABLE"
            for row in result["company_windows"]
        ),
        "industry_benchmark_unavailable_count": sum(
            row["industry_benchmark"]["status"] == "UNAVAILABLE"
            for row in result["company_windows"]
        ),
        "hard_failures": market_hard_failures(result),
        "formal_ready": False,
        "sha_gate": "DEFERRED",
    }
    (PACKAGE_ROOT / "market_validation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()
    if args.build:
        print(json.dumps(_build_outputs(), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
