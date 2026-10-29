"""Build an isolated read-only MySQL company enhancement candidate bundle."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence


DATASET_VERSION = "fingoose-mysql-company-enhancement-v1.0"
RELEASE_TIER = "VENDOR_CANDIDATE"
RATING_FIELDS = (
    "RATING_DT",
    "S_WRATING_AVG",
    "S_WRATING_INSTNUM",
    "S_WRATING_UPGRADE",
    "S_WRATING_DOWNGRADE",
    "S_WRATING_MAINTAIN",
    "S_WRATING_NUMOFBUY",
    "S_WRATING_NUMOFOUTPERFORM",
    "S_WRATING_NUMOFHOLD",
    "S_WRATING_NUMOFUNDERPERFORM",
    "S_WRATING_NUMOFSELL",
    "S_WRATING_CYCLE",
    "S_EST_PRICE",
    "S_EST_PRICEINSTNUM",
)
STATEMENT_TYPES = ("BALANCE_SHEET", "INCOME_STATEMENT", "CASH_FLOW")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, records: Iterable[Mapping[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(dict(record), ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _slug(value: str) -> str:
    return value.lower().replace(".", "-").replace("_", "-")


def _number(value: Any) -> int | float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper() == "NULL":
        return None
    try:
        result = float(text)
    except ValueError:
        return None
    return int(result) if result.is_integer() else result


def _date_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper() == "NULL" or text == "0":
        return None
    if re.fullmatch(r"\d{8}", text):
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def select_event_anchors(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    candidates = sorted(rows, key=lambda row: (str(row.get("event_id", "")), int(row.get("sequence", 10**9))))
    for row in candidates:
        event_id = str(row.get("event_id", ""))
        if not event_id or event_id in selected:
            continue
        if row.get("activation_mode") != "CAUSAL_CANDIDATE" or row.get("node_action") != "STARTS":
            continue
        anchor_date = _date_text(row.get("first_public_at"))
        if not anchor_date:
            continue
        selected[event_id] = {
            "anchor_id": row.get("anchor_id"),
            "fast_node_id": row.get("fast_node_id"),
            "anchor_date": anchor_date,
            "first_public_at": row.get("first_public_at"),
            "impact_tags": list(row.get("impact_tags") or []),
            "evidence_status": row.get("evidence_status"),
        }
    return selected


def industry_from_table_name(table_name: str) -> str | None:
    match = re.fullmatch(r"fr(.+)_history", table_name)
    return match.group(1) if match else None


def resolve_industry_membership(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    unique = {
        (str(row.get("industry", "")).strip(), str(row.get("source_table", "")).strip())
        for row in rows
        if str(row.get("industry", "")).strip()
    }
    memberships = [
        {"industry": industry, "source_table": source_table}
        for industry, source_table in sorted(unique)
    ]
    if not memberships:
        return {"status": "UNKNOWN", "industry": "UNKNOWN", "memberships": []}
    if len(memberships) == 1:
        return {"status": "MAPPED", "industry": memberships[0]["industry"], "memberships": memberships}
    return {"status": "AMBIGUOUS", "industry": "UNKNOWN", "memberships": memberships}


def _normalize_rating_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
    rating_date = _date_text(row.get("RATING_DT"))
    if not rating_date:
        return None
    return {
        "rating_date": rating_date,
        "rating_average": _number(row.get("S_WRATING_AVG")),
        "rating_institution_count": _number(row.get("S_WRATING_INSTNUM")),
        "upgrade_count": _number(row.get("S_WRATING_UPGRADE")),
        "downgrade_count": _number(row.get("S_WRATING_DOWNGRADE")),
        "maintain_count": _number(row.get("S_WRATING_MAINTAIN")),
        "buy_count": _number(row.get("S_WRATING_NUMOFBUY")),
        "outperform_count": _number(row.get("S_WRATING_NUMOFOUTPERFORM")),
        "hold_count": _number(row.get("S_WRATING_NUMOFHOLD")),
        "underperform_count": _number(row.get("S_WRATING_NUMOFUNDERPERFORM")),
        "sell_count": _number(row.get("S_WRATING_NUMOFSELL")),
        "rating_cycle": _number(row.get("S_WRATING_CYCLE")),
        "estimated_price": _number(row.get("S_EST_PRICE")),
        "estimated_price_institution_count": _number(row.get("S_EST_PRICEINSTNUM")),
    }


def _select_rating_observation(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    latest_date = max(str(row["rating_date"]) for row in rows)
    same_day = [dict(row) for row in rows if row["rating_date"] == latest_date]
    return max(
        same_day,
        key=lambda row: (
            row.get("rating_institution_count") if row.get("rating_institution_count") is not None else -1,
            row.get("estimated_price_institution_count") if row.get("estimated_price_institution_count") is not None else -1,
            json.dumps(row, ensure_ascii=False, sort_keys=True),
        ),
    )


def summarize_rating_rows(rows: Sequence[Mapping[str, Any]], anchor_date: str) -> dict[str, Any]:
    anchor = _parse_date(anchor_date)
    window_start = anchor - timedelta(days=60)
    window_end = anchor + timedelta(days=60)
    normalized = []
    for row in rows:
        item = _normalize_rating_row(row)
        if not item:
            continue
        current = _parse_date(item["rating_date"])
        if window_start <= current <= window_end:
            normalized.append(item)
    deduplicated = list({json.dumps(item, ensure_ascii=False, sort_keys=True): item for item in normalized}.values())
    deduplicated.sort(key=lambda item: (item["rating_date"], json.dumps(item, ensure_ascii=False, sort_keys=True)))
    pre_rows = [item for item in deduplicated if _parse_date(item["rating_date"]) < anchor]
    post_rows = [item for item in deduplicated if _parse_date(item["rating_date"]) >= anchor]
    pre = _select_rating_observation(pre_rows)
    post = _select_rating_observation(post_rows)
    deltas: dict[str, int | float | None] = {}
    for key in ("rating_average", "rating_institution_count", "estimated_price", "estimated_price_institution_count"):
        before = pre.get(key) if pre else None
        after = post.get(key) if post else None
        deltas[f"{key}_delta"] = round(float(after) - float(before), 10) if before is not None and after is not None else None
    return {
        "status": "WINDOW_DATA_AVAILABLE" if deduplicated else "NO_WINDOW_DATA",
        "association_only": True,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "selection_rule": "LATEST_DATE_THEN_MAX_RATING_INSTITUTION_COUNT",
        "raw_row_count": len(rows),
        "in_window_row_count": len(normalized),
        "duplicate_row_count": len(normalized) - len(deduplicated),
        "distinct_observation_count": len(deduplicated),
        "pre_event": {"observation_count": len(pre_rows), "selected_observation": pre},
        "post_event": {"observation_count": len(post_rows), "selected_observation": post},
        "deltas": deltas,
    }


def _normalize_financial_record(row: Mapping[str, Any]) -> dict[str, Any] | None:
    effective = _date_text(row.get("actual_ann_dt")) or _date_text(row.get("ann_dt"))
    if not effective:
        return None
    excluded = {
        "event_id", "company_code", "anchor_date", "statement_name", "object_id",
        "s_info_windcode", "wind_code", "ann_dt", "actual_ann_dt", "opdate", "opmode",
    }
    metrics: dict[str, Any] = {}
    for key, value in row.items():
        if key in excluded or key in {"report_period", "statement_type", "crncy_code"}:
            continue
        number = _number(value)
        if number is not None:
            metrics[key] = number
    return {
        "status": "PRE_EVENT_DATA_AVAILABLE",
        "effective_announcement_date": effective,
        "announcement_date": _date_text(row.get("ann_dt")),
        "actual_announcement_date": _date_text(row.get("actual_ann_dt")),
        "report_period": _date_text(row.get("report_period")),
        "statement_type": _number(row.get("statement_type")),
        "currency": row.get("crncy_code") if row.get("crncy_code") not in (None, "", "NULL") else None,
        "metrics": metrics,
    }


def select_financial_baseline(
    rows_by_statement: Mapping[str, Sequence[Mapping[str, Any]]], cutoff_date: str
) -> dict[str, Any]:
    cutoff = _parse_date(cutoff_date)
    result: dict[str, Any] = {}
    excluded_count = 0
    for statement in STATEMENT_TYPES:
        candidates = []
        for row in rows_by_statement.get(statement, []):
            item = _normalize_financial_record(row)
            if not item:
                continue
            if _parse_date(item["effective_announcement_date"]) > cutoff:
                excluded_count += 1
                continue
            candidates.append(item)
        if candidates:
            result[statement] = max(
                candidates,
                key=lambda item: (item["effective_announcement_date"], item.get("report_period") or ""),
            )
        else:
            result[statement] = {"status": "NO_PRE_EVENT_DATA"}
    result["excluded_post_event_count"] = excluded_count
    return result


def build_candidate_records(
    registry: Sequence[Mapping[str, Any]],
    anchors: Mapping[str, Mapping[str, Any]],
    memberships: Mapping[str, Sequence[Mapping[str, Any]]],
    rating_rows: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]],
    financial_rows: Mapping[tuple[str, str], Mapping[str, Sequence[Mapping[str, Any]]]],
) -> dict[str, list[dict[str, Any]]]:
    impact_candidates = []
    rating_windows = []
    financial_baselines = []
    for source in registry:
        event_id = str(source["event_id"])
        company_code = str(source["company_code"])
        company_name = str(source["company_name"])
        key = (event_id, company_code)
        anchor = dict(anchors.get(event_id) or {})
        anchor_date = anchor.get("anchor_date")
        industry = resolve_industry_membership(memberships.get(company_code, []))
        record_slug = f"{event_id}-{_slug(company_code)}"
        impact_candidates.append({
            "candidate_id": f"mysql-impact-{record_slug}",
            "dataset_version": DATASET_VERSION,
            "release_tier": RELEASE_TIER,
            "event_id": event_id,
            "anchor_id": anchor.get("anchor_id"),
            "anchor_date": anchor_date,
            "anchor_status": "ANCHOR_AVAILABLE" if anchor_date else "ANCHOR_UNKNOWN",
            "company_code": company_code,
            "company_name": company_name,
            "industry": industry["industry"],
            "industry_status": industry["status"],
            "industry_memberships": industry["memberships"],
            "impact_tags": list(anchor.get("impact_tags") or []),
            "status": "PROPOSED_UNVERIFIED",
            "official_company_exposure_verified": False,
            "causal_attribution_allowed": False,
            "source_class": "LICENSED_VENDOR_DATA",
        })
        if anchor_date:
            rating = summarize_rating_rows(rating_rows.get(key, []), anchor_date)
            financial = select_financial_baseline(financial_rows.get(key, {}), anchor_date)
        else:
            rating = {
                "status": "ANCHOR_UNKNOWN", "association_only": True, "pre_event": {"selected_observation": None},
                "post_event": {"selected_observation": None},
            }
            financial = {statement: {"status": "ANCHOR_UNKNOWN"} for statement in STATEMENT_TYPES}
            financial["excluded_post_event_count"] = 0
        rating_windows.append({
            "rating_window_id": f"mysql-rating-{record_slug}",
            "dataset_version": DATASET_VERSION,
            "release_tier": RELEASE_TIER,
            "event_id": event_id,
            "anchor_id": anchor.get("anchor_id"),
            "anchor_date": anchor_date,
            "company_code": company_code,
            "company_name": company_name,
            "source_table": "asharestockratingconsus_202607231014",
            **rating,
        })
        financial_baselines.append({
            "financial_baseline_id": f"mysql-financial-{record_slug}",
            "dataset_version": DATASET_VERSION,
            "release_tier": RELEASE_TIER,
            "event_id": event_id,
            "anchor_id": anchor.get("anchor_id"),
            "anchor_date": anchor_date,
            "company_code": company_code,
            "company_name": company_name,
            "source_tables": {
                "BALANCE_SHEET": "asharebalancesheet_202605261517",
                "INCOME_STATEMENT": "ashareincome_202605261519",
                "CASH_FLOW": "asharecashflow_202605261518",
            },
            "official_company_exposure_verified": False,
            **financial,
        })
    return {
        "impact_candidates": impact_candidates,
        "rating_windows": rating_windows,
        "financial_baselines": financial_baselines,
    }


class MysqlCliQueryRunner:
    def __init__(self, mysql_exe: Path, login_path: str, database: str) -> None:
        self.mysql_exe = Path(mysql_exe)
        self.login_path = login_path
        self.database = database

    def __call__(self, sql: str) -> list[dict[str, str]]:
        statement = sql.strip()
        trimmed = statement[:-1].rstrip() if statement.endswith(";") else statement
        first = re.match(r"^([A-Za-z]+)", trimmed)
        if not first or first.group(1).upper() not in {"SELECT", "SHOW", "DESCRIBE", "EXPLAIN", "WITH"}:
            raise ValueError("MySQL candidate builder permits read-only statements only")
        if ";" in trimmed or re.search(r"\b(INSERT|UPDATE|DELETE|REPLACE|ALTER|DROP|CREATE|TRUNCATE|GRANT|REVOKE|SET)\b", trimmed, re.I):
            raise ValueError("MySQL candidate builder permits read-only statements only")
        command = [
            str(self.mysql_exe),
            f"--login-path={self.login_path}",
            f"--database={self.database}",
            "--default-character-set=utf8mb4",
            "--batch",
            "--raw",
            "-e",
            trimmed,
        ]
        completed = subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8")
        if not completed.stdout.strip():
            return []
        return [dict(row) for row in csv.DictReader(completed.stdout.splitlines(), delimiter="\t")]


def _derived_candidates(registry: Sequence[Mapping[str, Any]], anchors: Mapping[str, Mapping[str, Any]]) -> str:
    parts = []
    for row in registry:
        event_id = str(row["event_id"])
        anchor_date = anchors.get(event_id, {}).get("anchor_date")
        if not anchor_date:
            continue
        compact = anchor_date.replace("-", "")
        start = (_parse_date(anchor_date) - timedelta(days=60)).strftime("%Y%m%d")
        end = (_parse_date(anchor_date) + timedelta(days=60)).strftime("%Y%m%d")
        parts.append(
            "SELECT "
            f"{_sql_string(event_id)} AS event_id,"
            f"{_sql_string(str(row['company_code']))} AS company_code,"
            f"{compact} AS anchor_date,{start} AS window_start,{end} AS window_end"
        )
    if not parts:
        raise ValueError("no registry companies have usable event anchors")
    return " UNION ALL ".join(parts)


def _load_live_mysql_rows(
    registry: Sequence[Mapping[str, Any]],
    anchors: Mapping[str, Mapping[str, Any]],
    query_runner: Callable[[str], list[dict[str, str]]],
) -> tuple[
    dict[str, list[dict[str, Any]]],
    dict[tuple[str, str], list[dict[str, Any]]],
    dict[tuple[str, str], dict[str, list[dict[str, Any]]]],
    list[dict[str, Any]],
]:
    company_codes = sorted({str(row["company_code"]) for row in registry})
    in_codes = ",".join(_sql_string(code) for code in company_codes)
    table_rows = query_runner(
        "SELECT TABLE_NAME FROM information_schema.tables "
        "WHERE table_schema=DATABASE() AND TABLE_NAME REGEXP '^fr.+_history$' ORDER BY TABLE_NAME"
    )
    industry_tables = [
        str(row["TABLE_NAME"] )
        for row in table_rows
        if industry_from_table_name(str(row["TABLE_NAME"] ))
    ]
    memberships: dict[str, list[dict[str, Any]]] = {code: [] for code in company_codes}
    source_manifest = []
    for table in industry_tables:
        industry = industry_from_table_name(table)
        if industry is None:
            continue
        rows = query_runner(f"SELECT 股票代码,股票简称 FROM `{table}` WHERE 股票代码 IN ({in_codes})")
        for row in rows:
            code = str(row.get("股票代码", ""))
            if code in memberships:
                memberships[code].append({"industry": industry, "source_table": table})
        source_manifest.append(_source_record(table, "COMPANY_INDUSTRY_MEMBERSHIP", len(rows)))

    derived = _derived_candidates(registry, anchors)
    rating_sql = (
        "SELECT c.event_id,c.company_code,c.anchor_date,r.RATING_DT,r.S_WRATING_AVG,r.S_WRATING_INSTNUM,"
        "r.S_WRATING_UPGRADE,r.S_WRATING_DOWNGRADE,r.S_WRATING_MAINTAIN,r.S_WRATING_NUMOFBUY,"
        "r.S_WRATING_NUMOFOUTPERFORM,r.S_WRATING_NUMOFHOLD,r.S_WRATING_NUMOFUNDERPERFORM,"
        "r.S_WRATING_NUMOFSELL,r.S_WRATING_CYCLE,r.S_EST_PRICE,r.S_EST_PRICEINSTNUM "
        f"FROM ({derived}) c JOIN asharestockratingconsus_202607231014 r "
        "ON r.S_INFO_WINDCODE=c.company_code AND r.RATING_DT BETWEEN c.window_start AND c.window_end"
    )
    rating_query_rows = query_runner(rating_sql)
    rating_rows: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rating_query_rows:
        key = (str(row["event_id"]), str(row["company_code"]))
        rating_rows.setdefault(key, []).append(row)
    source_manifest.append(_source_record("asharestockratingconsus_202607231014", "ANALYST_RATING_WINDOW", len(rating_query_rows)))

    statement_specs = {
        "BALANCE_SHEET": (
            "asharebalancesheet_202605261517",
            "ann_dt,actual_ann_dt,report_period,statement_type,crncy_code,tot_assets,tot_liab,monetary_cap,"
            "inventories,tot_cur_assets,tot_cur_liab,st_borrow,lt_borrow",
        ),
        "INCOME_STATEMENT": (
            "ashareincome_202605261519",
            "ann_dt,actual_ann_dt,report_period,statement_type,crncy_code,tot_oper_rev,oper_rev,oper_profit,"
            "net_profit_excl_min_int_inc,net_profit_incl_min_int_inc",
        ),
        "CASH_FLOW": (
            "asharecashflow_202605261518",
            "ann_dt,actual_ann_dt,report_period,statement_type,crncy_code,net_cash_flows_oper_act,"
            "net_cash_flows_inv_act,net_cash_flows_fnc_act,cash_cash_equ_end_period",
        ),
    }
    financial_rows: dict[tuple[str, str], dict[str, list[dict[str, Any]]]] = {}
    for statement, (table, fields) in statement_specs.items():
        rows = query_runner(
            f"SELECT c.event_id,c.company_code,c.anchor_date,{fields} FROM ({derived}) c "
            f"JOIN {table} f ON f.s_info_windcode=c.company_code"
        )
        for row in rows:
            key = (str(row["event_id"]), str(row["company_code"]))
            financial_rows.setdefault(key, {}).setdefault(statement, []).append(row)
        source_manifest.append(_source_record(table, statement, len(rows)))
    return memberships, rating_rows, financial_rows, source_manifest


def _source_record(table: str, purpose: str, selected_row_count: int) -> dict[str, Any]:
    return {
        "source_id": f"mysql-workspace-{_slug(table)}",
        "dataset_version": DATASET_VERSION,
        "source_class": "LICENSED_VENDOR_DATA",
        "database": "workspace",
        "table": table,
        "purpose": purpose,
        "selected_row_count": selected_row_count,
        "license_scope": "UNKNOWN",
        "display_allowed": False,
        "redistribution_allowed": False,
        "raw_vendor_rows_exposed": False,
        "credentials_included": False,
        "formal_source_status": "OFFICIAL_CROSSCHECK_REQUIRED",
    }


def _validate_records(records: Mapping[str, Sequence[Mapping[str, Any]]], expected_count: int) -> dict[str, Any]:
    hard_failures = []
    id_fields = {
        "impact_candidates": "candidate_id",
        "rating_windows": "rating_window_id",
        "financial_baselines": "financial_baseline_id",
    }
    for name, field in id_fields.items():
        rows = list(records[name])
        if len(rows) != expected_count:
            hard_failures.append(f"{name.upper()}_COUNT_MISMATCH")
        ids = [str(row.get(field, "")) for row in rows]
        if not all(ids) or len(ids) != len(set(ids)):
            hard_failures.append(f"{name.upper()}_ID_FAILURE")
    leakage = []
    for row in records["financial_baselines"]:
        cutoff = row.get("anchor_date")
        if not cutoff:
            continue
        for statement in STATEMENT_TYPES:
            selected = row.get(statement, {})
            effective = selected.get("effective_announcement_date")
            if effective and effective > cutoff:
                leakage.append({"financial_baseline_id": row["financial_baseline_id"], "statement": statement})
    if leakage:
        hard_failures.append("POST_EVENT_FINANCIAL_LEAKAGE")
    warnings = ["VENDOR_LICENSE_SCOPE_UNKNOWN", "OFFICIAL_COMPANY_EXPOSURE_STILL_REQUIRED"]
    ambiguous = sum(row.get("industry_status") == "AMBIGUOUS" for row in records["impact_candidates"])
    unknown = sum(row.get("industry_status") == "UNKNOWN" for row in records["impact_candidates"])
    missing_ratings = sum(row.get("status") != "WINDOW_DATA_AVAILABLE" for row in records["rating_windows"])
    missing_financials = sum(
        all(row.get(statement, {}).get("status") != "PRE_EVENT_DATA_AVAILABLE" for statement in STATEMENT_TYPES)
        for row in records["financial_baselines"]
    )
    return {
        "valid": not hard_failures,
        "hard_failures": hard_failures,
        "warnings": warnings,
        "expected_company_count": expected_count,
        "counts": {name: len(rows) for name, rows in records.items()},
        "industry_ambiguous_count": ambiguous,
        "industry_unknown_count": unknown,
        "rating_missing_count": missing_ratings,
        "financial_all_statements_missing_count": missing_financials,
        "post_event_financial_leakage": leakage,
        "formal_ready": False,
    }


def write_candidate_bundle(
    output_root: Path,
    records: Mapping[str, Sequence[Mapping[str, Any]]],
    source_manifest: Sequence[Mapping[str, Any]],
    validation: Mapping[str, Any],
    summary: Mapping[str, Any],
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output_root / "company_impact_candidates.jsonl", records["impact_candidates"])
    _write_jsonl(output_root / "company_rating_windows.jsonl", records["rating_windows"])
    _write_jsonl(output_root / "company_financial_baselines.jsonl", records["financial_baselines"])
    _write_jsonl(output_root / "source_manifest.jsonl", source_manifest)
    _write_json(output_root / "validation_report.json", validation)
    _write_json(output_root / "summary.json", summary)
    (output_root / "README.md").write_text(
        "# MySQL Company Enhancement Candidate\n\n"
        "Read-only vendor candidate outputs for industry membership, analyst-rating windows, and pre-event financial baselines.\n\n"
        "The bundle is not formal evidence, does not verify company exposure, and cannot be redistributed until vendor licensing is resolved.\n",
        encoding="utf-8",
    )
    emitted = [
        output_root / "company_impact_candidates.jsonl",
        output_root / "company_rating_windows.jsonl",
        output_root / "company_financial_baselines.jsonl",
        output_root / "source_manifest.jsonl",
        output_root / "validation_report.json",
        output_root / "summary.json",
        output_root / "README.md",
    ]
    manifest = {
        "dataset_version": DATASET_VERSION,
        "release_tier": RELEASE_TIER,
        "formal_ready": False,
        "files": [
            {
                "path": path.name,
                "record_count": sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
                if path.suffix == ".jsonl" else 1,
                "sha256": _sha256(path),
            }
            for path in emitted
        ],
    }
    _write_json(output_root / "manifest.json", manifest)
    return manifest


def build_mysql_company_enhancement(
    root: Path,
    output_root: Path,
    login_path: str = "fingoose-codex",
    database: str = "workspace",
    mysql_exe: Path = Path("D:/mysql/bin/mysql.exe"),
    query_runner: Callable[[str], list[dict[str, str]]] | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    output_root = output_root.resolve()
    protected = [(root / name).resolve() for name in ("data", "code", "ui")]
    if any(output_root == path or path in output_root.parents for path in protected):
        raise ValueError("output_root must remain outside protected production and UI directories")
    registry = _read_jsonl(root / "data/company_candidate_v1/candidate_company_registry.jsonl")
    anchor_rows = _read_jsonl(root / "work/transmission_24_anchor_v2_candidate/anchor_catalog.jsonl")
    anchors = select_event_anchors(anchor_rows)
    runner = query_runner or MysqlCliQueryRunner(mysql_exe=mysql_exe, login_path=login_path, database=database)
    memberships, rating_rows, financial_rows, source_manifest = _load_live_mysql_rows(registry, anchors, runner)
    records = build_candidate_records(registry, anchors, memberships, rating_rows, financial_rows)
    validation = _validate_records(records, len(registry))
    summary = {
        "dataset_version": DATASET_VERSION,
        "release_tier": RELEASE_TIER,
        "candidate_ready": validation["valid"],
        "formal_ready": False,
        "display_allowed": False,
        "redistribution_allowed": False,
        "company_candidate_count": len(records["impact_candidates"]),
        "industry_mapped_count": sum(row["industry_status"] == "MAPPED" for row in records["impact_candidates"]),
        "rating_window_available_count": sum(row["status"] == "WINDOW_DATA_AVAILABLE" for row in records["rating_windows"]),
        "financial_baseline_available_count": sum(
            any(row[statement].get("status") == "PRE_EVENT_DATA_AVAILABLE" for statement in STATEMENT_TYPES)
            for row in records["financial_baselines"]
        ),
        "formal_blockers": [
            "VENDOR_LICENSE_SCOPE_UNKNOWN",
            "OFFICIAL_COMPANY_EXPOSURE_REQUIRED",
            "A_SHARE_PRICE_WINDOWS_NOT_AVAILABLE",
            "INDEPENDENT_REVIEW_REQUIRED",
        ],
    }
    write_candidate_bundle(output_root, records, source_manifest, validation, summary)
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("work/mysql_company_enhancement_v1_candidate"))
    parser.add_argument("--login-path", default="fingoose-codex")
    parser.add_argument("--database", default="workspace")
    parser.add_argument("--mysql-exe", type=Path, default=Path("D:/mysql/bin/mysql.exe"))
    args = parser.parse_args(argv)
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    summary = build_mysql_company_enhancement(
        root=root,
        output_root=output,
        login_path=args.login_path,
        database=args.database,
        mysql_exe=args.mysql_exe,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
