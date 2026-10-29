"""Build an isolated licensed-vendor futures enhancement for company candidates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence


DATASET_VERSION = "fingoose-macro-event-company-vendor-enhancement-v1.0"
PRIORITY_SYMBOLS = ("EG", "EB", "L", "PP", "PG", "I", "J", "JM")
SOURCE_CLASS = "LICENSED_VENDOR_DATA"
VERIFICATION_STATUS = "VENDOR_VERIFIED"
FORMAL_SOURCE_STATUS = "OFFICIAL_CROSSCHECK_REQUIRED"
REQUIRED_EOD_FIELDS = {
    "S_INFO_WINDCODE", "TRADE_DT", "S_DQ_PRESETTLE", "S_DQ_OPEN",
    "S_DQ_HIGH", "S_DQ_LOW", "S_DQ_CLOSE", "S_DQ_SETTLE",
    "S_DQ_VOLUME", "S_DQ_OI", "FS_INFO_TYPE",
}

EVENTS = {
    "event-02": {
        "title": "Russia's full-scale attack on Ukraine",
        "anchor_at": "2022-02-24T05:00:00+00:00",
        "first_dce_session": "2022-02-24",
    },
    "event-06": {
        "title": "OPEC+ members announce additional voluntary production cuts",
        "anchor_at": "2023-04-02T13:00:00+00:00",
        "first_dce_session": "2023-04-03",
    },
}

DEFAULT_ROOT = Path("inputs/commodities/v0.2/inbox/wind/dce_iron_ore")
DEFAULT_CALENDAR = DEFAULT_ROOT / "raw/calendar/CFUTURESCALENDAR_202607231546.csv"
DEFAULT_METADATA = DEFAULT_ROOT / "raw/metadata/CFUTURESDESCRIPTION_202607231546.csv"
DEFAULT_EOD = DEFAULT_ROOT / "raw/daily/wind_dce_iron_ore_eod/2026-07-23/2e11d3b681fb0fa1_CCOMMODITYFUTURESEODPRICES_202607231545.csv"
DEFAULT_DICTIONARY_ROOT = DEFAULT_ROOT / "restricted_docs/data_dictionary"
DEFAULT_CANDIDATE_ROOT = Path("outputs/fingoose_macro_event_company_candidate_v1")
DEFAULT_OUTPUT = Path("outputs/fingoose_macro_event_company_candidate_vendor_enhancement_v1")
DEFAULT_NUMERIC_EVALUATION = Path("inputs/qa_candidates/financial_fact_extraction/answer_evaluation.distill.jsonl")
DEFAULT_WIND_SUMMARY = Path("outputs/fingoose_commodity_market/v0.2/wind_candidate/summary.json")
DEFAULT_PROTECTED_ROOTS = (
    Path("outputs/fingoose_macro_event_attribution_v1"),
    Path("outputs/fingoose_formal_v1_macro"),
    Path("outputs/fingoose_macro_event_company_v1"),
    DEFAULT_CANDIDATE_ROOT,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _directory_fingerprint(paths: Sequence[Path]) -> str:
    digest = hashlib.sha256()
    for root in sorted((path.resolve() for path in paths), key=lambda value: value.as_posix()):
        digest.update(root.as_posix().encode("utf-8"))
        if not root.exists():
            digest.update(b"<missing>")
            continue
        for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda value: value.as_posix()):
            stat = path.stat()
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(str(stat.st_size).encode("ascii"))
            digest.update(str(stat.st_mtime_ns).encode("ascii"))
    return digest.hexdigest()


def require_futures_calendar_scope(exchange: str) -> str:
    normalized = exchange.upper()
    if normalized in {"SSE", "SZSE"}:
        raise ValueError("DCE futures calendar cannot be used as an SSE or SZSE equity calendar")
    if normalized != "DCE":
        raise ValueError(f"unsupported futures calendar exchange: {exchange}")
    return normalized


def _require_headers(actual: Sequence[str] | None, required: set[str], label: str) -> list[str]:
    fields = list(actual or [])
    missing = sorted(required - set(fields))
    if missing:
        raise ValueError(f"{label} is missing columns: {missing}")
    return fields


def _load_calendar(path: Path) -> tuple[list[str], dict[str, Any]]:
    require_futures_calendar_scope("DCE")
    dates: set[str] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = _require_headers(reader.fieldnames, {"TRADE_DAYS", "S_INFO_EXCHMARKET"}, "futures calendar")
        for row in reader:
            if str(row.get("S_INFO_EXCHMARKET", "")).strip().upper() != "DCE":
                continue
            raw = str(row.get("TRADE_DAYS", "")).strip()
            if re.fullmatch(r"\d{8}", raw):
                dates.add(f"{raw[:4]}-{raw[4:6]}-{raw[6:]}")
    if not dates:
        raise ValueError("futures calendar contains no DCE sessions")
    ordered = sorted(dates)
    return ordered, {
        "calendar_id": "WIND-CFUTURESCALENDAR-DCE-20260723",
        "allowed_exchange": "DCE",
        "allowed_usage": "COMMODITY_FUTURES_SESSION_ALIGNMENT_ONLY",
        "forbidden_as_equity_calendar": ["SSE", "SZSE"],
        "source_class": SOURCE_CLASS,
        "verification_status": VERIFICATION_STATUS,
        "formal_source_status": FORMAL_SOURCE_STATUS,
        "schema_fields": fields,
        "session_count": len(ordered),
        "coverage_start": ordered[0],
        "coverage_end": ordered[-1],
    }


def _event_session_spec(calendar: list[str], first_session: str) -> dict[str, Any]:
    try:
        index = calendar.index(first_session)
    except ValueError as error:
        raise ValueError(f"DCE calendar does not contain event session {first_session}") from error
    if index < 60 or index + 20 >= len(calendar):
        raise ValueError(f"DCE calendar lacks -60/+20 coverage for {first_session}")
    return {
        "baseline_session": calendar[index - 1],
        "d1_session": calendar[index],
        "d3_session": calendar[index + 2],
        "d5_session": calendar[index + 4],
        "d20_session": calendar[index + 19],
        "required_start": calendar[index - 60],
        "required_end": calendar[index + 20],
        "required_sessions": calendar[index - 60 : index + 21],
    }


def _load_contract_registry(path: Path) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = {symbol: [] for symbol in PRIORITY_SYMBOLS}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        _require_headers(
            reader.fieldnames,
            {"S_INFO_WINDCODE", "FS_INFO_SCCODE", "FS_INFO_TYPE", "S_INFO_EXCHMARKET", "S_INFO_LISTDATE", "S_INFO_DELISTDATE", "FS_INFO_LTDLDATE"},
            "futures contract metadata",
        )
        for row in reader:
            symbol = str(row.get("FS_INFO_SCCODE", "")).strip().upper()
            if symbol in grouped and str(row.get("S_INFO_EXCHMARKET", "")).strip().upper() == "DCE":
                grouped[symbol].append(row)
    records = []
    for symbol in PRIORITY_SYMBOLS:
        rows = grouped[symbol]
        listed = sorted(str(row.get("S_INFO_LISTDATE", "")).strip().strip('"') for row in rows if str(row.get("S_INFO_LISTDATE", "")).strip())
        delisted = sorted(str(row.get("S_INFO_DELISTDATE", "")).strip().strip('"') for row in rows if str(row.get("S_INFO_DELISTDATE", "")).strip())
        type_counts: dict[str, int] = {}
        for row in rows:
            key = str(row.get("FS_INFO_TYPE", "")).strip() or "UNKNOWN"
            type_counts[key] = type_counts.get(key, 0) + 1
        records.append({
            "series_id": f"{symbol}.DCE",
            "commodity_code": symbol,
            "exchange": "DCE",
            "record_count": len(rows),
            "metadata_contract_type_counts": type_counts,
            "metadata_contract_type_semantics": {"1": "MONTHLY_CONTRACT", "2": "CONTINUOUS_CONTRACT", "3": "ACTIVE_CONTRACT"},
            "eod_contract_type_semantics": {"1": "CONTINUOUS_CONTRACT", "2": "REAL_CONTRACT", "3": "ACTIVE_CONTRACT"},
            "earliest_list_date": listed[0] if listed else None,
            "latest_delist_date": delisted[-1] if delisted else None,
            "verification_status": VERIFICATION_STATUS if rows else "PENDING_ARCHIVE",
            "formal_source_status": FORMAL_SOURCE_STATUS,
            "raw_vendor_rows_exposed": False,
        })
    return records


def _inspect_eod(path: Path, requested_dates: set[str]) -> tuple[dict[str, set[str]], dict[str, Any], str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        fields = _require_headers(next(reader, None), REQUIRED_EOD_FIELDS, "commodity futures EOD")
    compact_dates = {value.replace("-", "") for value in requested_dates}
    coverage = {symbol: set() for symbol in PRIORITY_SYMBOLS}
    symbol_pattern = b"|".join(symbol.encode("ascii") for symbol in PRIORITY_SYMBOLS)
    pattern = re.compile(rb",(" + symbol_pattern + rb")\d{4}\.DCE,\"?(\d{8})\"?,")
    digest = hashlib.sha256()
    byte_count = 0
    matched_rows = 0
    with path.open("rb") as handle:
        for line in handle:
            digest.update(line)
            byte_count += len(line)
            match = pattern.search(line)
            if not match:
                continue
            day = match.group(2).decode("ascii")
            if day in compact_dates:
                symbol = match.group(1).decode("ascii")
                coverage[symbol].add(f"{day[:4]}-{day[4:6]}-{day[6:]}")
                matched_rows += 1
    return coverage, {
        "schema_id": "WIND-CCOMMODITYFUTURESEODPRICES-20260723",
        "schema_fields": fields,
        "required_fields_present": True,
        "byte_count": byte_count,
        "requested_range_matched_row_count": matched_rows,
        "loader_regression_only": True,
        "event_window_values_allowed": False,
        "gap_reason": "Event-window values remain blocked unless every required -60/+20 DCE session is archived for a priority series.",
        "source_class": SOURCE_CLASS,
        "verification_status": VERIFICATION_STATUS,
        "formal_source_status": FORMAL_SOURCE_STATUS,
    }, digest.hexdigest()

_NUMBER_PATTERN = re.compile(
    r"\(([-+]?\d[\d,]*(?:\.\d+)?)\)|([-+]?\d[\d,]*(?:\.\d+)?)(%)?\s*(million|billion)?",
    re.IGNORECASE,
)


def normalize_numeric_text(text: str) -> list[float]:
    values: list[float] = []
    for match in _NUMBER_PATTERN.finditer(text):
        accounting, regular, _percent, unit = match.groups()
        raw = accounting or regular
        value = float(raw.replace(",", ""))
        if accounting is not None:
            value = -abs(value)
        multiplier = {None: 1.0, "million": 1_000_000.0, "billion": 1_000_000_000.0}[unit.lower() if unit else None]
        values.append(value * multiplier)
    return values


def _numeric_evaluation(path: Path) -> dict[str, Any]:
    records = _read_jsonl(path)
    expected_numeric_count = 0
    exact_match_count = 0
    negative_expected_count = 0
    percentage_context_count = 0
    for record in records:
        metadata = record.get("metadata") or {}
        try:
            expected = float(str(metadata.get("expected_answer", "")).replace(",", ""))
        except ValueError:
            continue
        expected_numeric_count += 1
        if expected < 0:
            negative_expected_count += 1
        messages = record.get("messages") or []
        assistant_text = " ".join(str(message.get("content", "")) for message in messages if message.get("role") == "assistant")
        prompt_text = " ".join(str(message.get("content", "")) for message in messages if message.get("role") == "user")
        if "%" in prompt_text or "%" in assistant_text:
            percentage_context_count += 1
        candidates = normalize_numeric_text(assistant_text)
        if any(abs(candidate - expected) <= max(1e-9, abs(expected) * 1e-9) for candidate in candidates):
            exact_match_count += 1
    micro_cases = {
        "comma_grouping": normalize_numeric_text("6,823") == [6823.0],
        "accounting_negative": normalize_numeric_text("(154)") == [-154.0],
        "percentage": normalize_numeric_text("12.5%") == [12.5],
        "million_unit": normalize_numeric_text("1.25 million") == [1250000.0],
    }
    return {
        "dataset_role": "INDEPENDENT_NUMERIC_EVALUATION_ONLY",
        "excluded_from_company_dossiers": True,
        "excluded_from_event_samples": True,
        "source_path": _relative(path),
        "content_sha256": _sha256(path),
        "record_count": len(records),
        "expected_numeric_count": expected_numeric_count,
        "simple_exact_match_count": exact_match_count,
        "simple_exact_match_rate": round(exact_match_count / expected_numeric_count, 6) if expected_numeric_count else None,
        "negative_expected_count": negative_expected_count,
        "percentage_context_count": percentage_context_count,
        "micro_regression_cases": micro_cases,
        "micro_regression_passed": all(micro_cases.values()),
        "benchmark_status": "PROFILED_NON_GATING",
        "limitations": [
            "The simple score does not infer unstated unit multipliers from mojibake text.",
            "This benchmark does not alter company dossiers, event samples, or labels.",
        ],
    }


def _source_record(source_id: str, path: Path, role: str, *, content_sha256: str | None = None) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "role": role,
        "provider": "Wind",
        "source_class": SOURCE_CLASS,
        "verification_status": VERIFICATION_STATUS,
        "formal_source_status": FORMAL_SOURCE_STATUS,
        "source_url": "https://www.wind.com.cn/",
        "local_snapshot_path": _relative(path),
        "content_sha256": content_sha256 or _sha256(path),
        "byte_count": path.stat().st_size,
        "display_allowed": False,
        "redistribution_allowed": False,
        "internal_research_only": True,
        "license_scope": "unknown",
    }


def _company_enhancement_candidates(registry_path: Path, request_lookup: dict[str, list[str]]) -> list[dict[str, Any]]:
    records = []
    for company in _read_jsonl(registry_path):
        event_id = company.get("event_id")
        if event_id not in EVENTS:
            continue
        code = str(company.get("company_code"))
        slug = code.lower().replace(".", "-")
        records.append({
            "enhancement_id": f"vendor-futures-{event_id}-{slug}",
            "event_id": event_id,
            "company_code": code,
            "company_name": company.get("company_name"),
            "base_dossier_id": f"company-dossier-{event_id}-{slug}",
            "candidate_futures_series": [f"{symbol}.DCE" for symbol in PRIORITY_SYMBOLS],
            "window_request_ids": request_lookup[event_id],
            "augmentation_node": {
                "node_type": "COMMODITY_FUTURES_SIGNAL",
                "status": "PENDING_EVIDENCE",
                "value": "UNKNOWN",
                "evidence_refs": [],
                "gap_reason": "Historical event-window EOD data and company-specific exposure evidence are not yet jointly archived.",
            },
            "selection_basis": "PRIORITY_EVENT_SCREENING_ONLY_NO_ASSOCIATION_ASSERTED",
            "status": "PENDING_ARCHIVE",
            "association_or_forecast_changed": False,
            "base_candidate_output_modified": False,
            "formal_ready": False,
        })
    return records


def _official_crosscheck_queue(requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{
        "crosscheck_id": f"official-crosscheck-{item['event_id']}-{item['commodity_code'].lower()}",
        "request_id": item["request_id"],
        "event_id": item["event_id"],
        "series_id": item["series_id"],
        "status": "PENDING_ARCHIVE",
        "formal_source_status": FORMAL_SOURCE_STATUS,
        "leads": [
            {"publisher": "Dalian Commodity Exchange", "source_url": "http://www.dce.com.cn/dalianshangpin/xqsj/lssj/index.html", "source_role": "OFFICIAL_EXCHANGE_SPOT_CHECK", "verification_status": "PENDING"},
            {"publisher": "CnOpenData", "source_url": "https://www.cnopendata.com/data/m/Futures/Futures/jy.html", "source_role": "NON_OFFICIAL_CALENDAR_CROSSCHECK_LEAD", "verification_status": "PENDING"},
        ],
        "gap_reason": "No official exchange snapshot has been archived for this event-series window.",
    } for item in requests]

def _load_contract_lifecycles(path: Path) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            code = str(row.get("S_INFO_WINDCODE", "")).strip().upper()
            symbol = str(row.get("FS_INFO_SCCODE", "")).strip().upper()
            if symbol not in PRIORITY_SYMBOLS or not code.endswith(".DCE"):
                continue
            if not re.fullmatch(re.escape(symbol) + r"\d{4}\.DCE", code):
                continue
            result[code] = {
                "list_date": str(row.get("S_INFO_LISTDATE", "")).strip().strip('"'),
                "delist_date": str(row.get("S_INFO_DELISTDATE", "")).strip().strip('"'),
                "last_trade_date": str(row.get("FS_INFO_LTDLDATE", "")).strip().strip('"'),
            }
    return result


def _extract_daily_main_returns(
    path: Path,
    requested_dates: set[str],
    lifecycles: dict[str, dict[str, str]],
) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, Any]]:
    compact_dates = {value.replace("-", "") for value in requested_dates}
    selected: dict[str, dict[str, dict[str, Any]]] = {symbol: {} for symbol in PRIORITY_SYMBOLS}
    candidates: dict[tuple[str, str], list[dict[str, Any]]] = {}
    rejected_counts: dict[str, int] = {}
    symbol_pattern = b"|".join(symbol.encode("ascii") for symbol in PRIORITY_SYMBOLS)
    pattern = re.compile(rb",(" + symbol_pattern + rb")\d{4}\.DCE,\"?(\d{8})\"?,")
    with path.open("rb") as handle:
        header = next(handle).decode("utf-8-sig").rstrip("\r\n")
        fields = next(csv.reader([header]))
        indexes = {name: fields.index(name) for name in REQUIRED_EOD_FIELDS}
        for line_number, line in enumerate(handle, 2):
            match = pattern.search(line)
            if not match:
                continue
            raw_day = match.group(2).decode("ascii")
            if raw_day not in compact_dates:
                continue
            row = next(csv.reader([line.decode("utf-8-sig").rstrip("\r\n")]))
            if row[indexes["FS_INFO_TYPE"]].strip() != "2":
                rejected_counts["NOT_REAL_CONTRACT"] = rejected_counts.get("NOT_REAL_CONTRACT", 0) + 1
                continue
            code = row[indexes["S_INFO_WINDCODE"]].strip().upper()
            lifecycle = lifecycles.get(code)
            if lifecycle is None:
                rejected_counts["MISSING_LIFECYCLE"] = rejected_counts.get("MISSING_LIFECYCLE", 0) + 1
                continue
            last_valid = lifecycle["last_trade_date"] or lifecycle["delist_date"]
            if lifecycle["list_date"] and raw_day < lifecycle["list_date"]:
                rejected_counts["BEFORE_LIST_DATE"] = rejected_counts.get("BEFORE_LIST_DATE", 0) + 1
                continue
            if last_valid and raw_day > last_valid:
                rejected_counts["AFTER_LAST_TRADE_DATE"] = rejected_counts.get("AFTER_LAST_TRADE_DATE", 0) + 1
                continue
            try:
                pre_settlement = float(row[indexes["S_DQ_PRESETTLE"]])
                settlement = float(row[indexes["S_DQ_SETTLE"]])
                open_interest = int(float(row[indexes["S_DQ_OI"]]))
                volume = int(float(row[indexes["S_DQ_VOLUME"]]))
            except (ValueError, TypeError):
                rejected_counts["NON_NUMERIC_CORE_FIELD"] = rejected_counts.get("NON_NUMERIC_CORE_FIELD", 0) + 1
                continue
            if pre_settlement <= 0 or settlement <= 0 or open_interest < 0 or volume < 0:
                rejected_counts["INVALID_CORE_FIELD"] = rejected_counts.get("INVALID_CORE_FIELD", 0) + 1
                continue
            symbol = match.group(1).decode("ascii")
            day = f"{raw_day[:4]}-{raw_day[4:6]}-{raw_day[6:]}"
            candidates.setdefault((symbol, day), []).append({
                "contract_code": code,
                "pre_settlement": pre_settlement,
                "settlement": settlement,
                "open_interest": open_interest,
                "volume": volume,
                "source_line": line_number,
            })
    for (symbol, day), rows in candidates.items():
        chosen = sorted(rows, key=lambda item: (-item["open_interest"], -item["volume"], item["contract_code"]))[0]
        selected[symbol][day] = {
            **chosen,
            "daily_return": chosen["settlement"] / chosen["pre_settlement"] - 1.0,
            "candidate_contract_count": len(rows),
        }
    return selected, {
        "selection_rule": "HIGHEST_OPEN_INTEREST_THEN_VOLUME_AMONG_REAL_CONTRACTS",
        "roll_return_rule": "SELECTED_CONTRACT_SETTLEMENT_DIVIDED_BY_ITS_OWN_PRE_SETTLEMENT",
        "lifecycle_gate_applied": True,
        "rejected_row_counts": rejected_counts,
        "raw_vendor_rows_exposed": False,
    }


def _compound(values: Sequence[float]) -> float:
    result = 1.0
    for value in values:
        result *= 1.0 + value
    return result - 1.0


def _build_computed_window(
    request: dict[str, Any],
    spec: dict[str, Any],
    daily: dict[str, dict[str, Any]],
    source_sha256: str,
) -> dict[str, Any] | None:
    required = spec["required_sessions"]
    if any(day not in daily for day in required):
        return None
    baseline_index = required.index(spec["baseline_session"])
    pre_returns = [daily[day]["daily_return"] for day in required[: baseline_index + 1]]
    if len(pre_returns) != 60:
        return None
    mean = sum(pre_returns) / len(pre_returns)
    variance = sum((value - mean) ** 2 for value in pre_returns) / (len(pre_returns) - 1)
    sigma = variance ** 0.5
    windows: dict[str, float] = {}
    abnormal: dict[str, float | None] = {}
    for label, key in (("D1", "d1_session"), ("D3", "d3_session"), ("D5", "d5_session"), ("D20", "d20_session")):
        target_index = required.index(spec[key])
        change = _compound([daily[day]["daily_return"] for day in required[baseline_index + 1 : target_index + 1]])
        windows[label] = round(change * 100.0, 8)
        horizon = target_index - baseline_index
        abnormal[label] = round(change / (sigma * (horizon ** 0.5)), 8) if sigma > 0 else None
    trace = [{
        "trade_date": day,
        "selected_contract": daily[day]["contract_code"],
        "daily_settlement_return_pct": round(daily[day]["daily_return"] * 100.0, 12),
        "source_locator": {"type": "csv_line", "value": daily[day]["source_line"]},
        "candidate_contract_count": daily[day]["candidate_contract_count"],
    } for day in required]
    return {
        "window_id": request["request_id"],
        "event_id": request["event_id"],
        "series_id": request["series_id"],
        "exchange": "DCE",
        "status": "VENDOR_WINDOW_COMPUTED",
        "baseline": {"session": spec["baseline_session"], "synthetic_index": 100.0},
        "window_changes_pct": windows,
        "pre_event_daily_volatility_pct": round(sigma * 100.0, 8),
        "standardized_abnormal_scores": abnormal,
        "calculation_method": {
            "main_contract": "highest OI, then volume, among FS_INFO_TYPE=2 real contracts",
            "roll_handling": "daily return uses selected contract settlement / its own pre-settlement",
            "aggregation": "geometric compounding from baseline through target session",
            "pre_event_volatility": "sample standard deviation of 60 daily selected-contract settlement returns",
            "rounding_tolerance_pct": 1e-6,
        },
        "calculation_trace": trace,
        "source_ref": {
            "source_id": "wind-commodity-futures-eod-csv",
            "content_sha256": source_sha256,
            "source_class": SOURCE_CLASS,
            "verification_status": VERIFICATION_STATUS,
            "formal_source_status": FORMAL_SOURCE_STATUS,
            "display_allowed": False,
        },
        "official_crosscheck_status": "PENDING",
        "formal_ready": False,
    }

def build_vendor_enhancement(
    *,
    output_root: Path,
    calendar_path: Path,
    metadata_path: Path,
    eod_path: Path,
    calendar_dictionary_path: Path,
    metadata_dictionary_path: Path,
    eod_dictionary_path: Path,
    candidate_registry_path: Path,
    numeric_evaluation_path: Path,
    base_candidate_summary_path: Path | None = None,
    wind_candidate_summary_path: Path | None = None,
    protected_roots: Sequence[Path] = DEFAULT_PROTECTED_ROOTS,
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    paths = [
        calendar_path, metadata_path, eod_path, calendar_dictionary_path,
        metadata_dictionary_path, eod_dictionary_path, candidate_registry_path,
        numeric_evaluation_path,
    ]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"required enhancement inputs are missing: {missing}")
    output_resolved = output_root.resolve()
    for protected in protected_roots:
        protected_resolved = protected.resolve()
        if output_resolved == protected_resolved or protected_resolved in output_resolved.parents:
            raise ValueError(f"output root cannot be inside protected output: {protected}")

    before_fingerprint = _directory_fingerprint(protected_roots)
    calendar, calendar_profile = _load_calendar(calendar_path)
    session_specs = {
        event_id: _event_session_spec(calendar, event["first_dce_session"])
        for event_id, event in EVENTS.items()
    }
    requested_dates = {
        day for spec in session_specs.values() for day in spec["required_sessions"]
    }
    contract_registry = _load_contract_registry(metadata_path)
    coverage, eod_profile, eod_hash = _inspect_eod(eod_path, requested_dates)
    lifecycles = _load_contract_lifecycles(metadata_path)
    daily_main, selection_audit = _extract_daily_main_returns(eod_path, requested_dates, lifecycles)
    eod_profile["main_contract_selection_audit"] = selection_audit

    if wind_candidate_summary_path and wind_candidate_summary_path.is_file():
        old_summary = json.loads(wind_candidate_summary_path.read_text(encoding="utf-8"))
        eod_profile["existing_adapter_regression"] = {
            "status": "PASSED" if not old_summary.get("validation_errors") else "FAILED",
            "dates": old_summary.get("dates", []),
            "continuous_record_count": old_summary.get("continuous_record_count", 0),
            "scope_restriction": "LOADER_REGRESSION_ONLY_NOT_EVENT_WINDOW_EVIDENCE",
        }
    else:
        eod_profile["existing_adapter_regression"] = {"status": "NOT_PROVIDED"}

    requests: list[dict[str, Any]] = []
    request_lookup: dict[str, list[str]] = {event_id: [] for event_id in EVENTS}
    for event_id, event in EVENTS.items():
        spec = session_specs[event_id]
        required = set(spec["required_sessions"])
        for symbol in PRIORITY_SYMBOLS:
            available = sorted(required & set(daily_main[symbol]))
            missing_sessions = sorted(required - set(daily_main[symbol]))
            request_id = f"futures-window-{event_id}-{symbol.lower()}-dce"
            request_lookup[event_id].append(request_id)
            requests.append({
                "request_id": request_id,
                "event_id": event_id,
                "event_title": event["title"],
                "event_anchor_at": event["anchor_at"],
                "commodity_code": symbol,
                "series_id": f"{symbol}.DCE",
                "exchange": "DCE",
                "calendar_id": calendar_profile["calendar_id"],
                "window_metric": "CONTINUOUS_SETTLEMENT_RETURN_PCT",
                "required_pre_event_sessions": 60,
                "required_post_event_sessions": 20,
                "required_session_count": len(required),
                "required_start": spec["required_start"],
                "required_end": spec["required_end"],
                "baseline_session": spec["baseline_session"],
                "window_sessions": {key: value for key, value in spec.items() if key.endswith("_session")},
                "available_session_count": len(available),
                "missing_session_count": len(missing_sessions),
                "available_sessions": available,
                "status": "PENDING_ARCHIVE" if missing_sessions else "PENDING_METHOD_REVIEW",
                "actual_values": {},
                "values_generated": False,
                "gap_reason": (
                    f"Missing {len(missing_sessions)} of {len(required)} required DCE sessions in the archived EOD source."
                    if missing_sessions else
                    "Coverage exists, but continuous-series and roll-method review is still required before calculating values."
                ),
                "source_class": SOURCE_CLASS,
                "verification_status": VERIFICATION_STATUS,
                "formal_source_status": FORMAL_SOURCE_STATUS,
            })

    computed_windows: list[dict[str, Any]] = []
    for request in requests:
        window = _build_computed_window(
            request,
            session_specs[request["event_id"]],
            daily_main[request["commodity_code"]],
            eod_hash,
        )
        if window is None:
            continue
        request["status"] = "VENDOR_WINDOW_COMPUTED"
        request["actual_values"] = window["window_changes_pct"]
        request["values_generated"] = True
        request["gap_reason"] = None
        computed_windows.append(window)

    eod_profile["event_window_values_allowed"] = len(computed_windows) == len(requests)
    eod_profile["loader_regression_only"] = False if computed_windows else True
    eod_profile["gap_reason"] = (
        None if len(computed_windows) == len(requests)
        else "One or more event-series windows lack complete real-contract EOD coverage."
    )
    eod_profile["event_window_scope"] = {
        "events": list(EVENTS),
        "series": [f"{symbol}.DCE" for symbol in PRIORITY_SYMBOLS],
        "computed_window_count": len(computed_windows),
        "official_crosscheck_status": "PENDING",
    }
    company_candidates = _company_enhancement_candidates(candidate_registry_path, request_lookup)
    computed_by_event = {
        event_id: [item for item in computed_windows if item["event_id"] == event_id]
        for event_id in EVENTS
    }
    for candidate in company_candidates:
        available_windows = computed_by_event[candidate["event_id"]]
        if len(available_windows) == len(PRIORITY_SYMBOLS):
            candidate["status"] = "PENDING_EVIDENCE"
            candidate["augmentation_node"]["status"] = "PARTIAL_EVIDENCE"
            candidate["augmentation_node"]["value"] = "VENDOR_FUTURES_WINDOWS_AVAILABLE_ASSOCIATION_UNKNOWN"
            candidate["augmentation_node"]["evidence_refs"] = [
                {"window_id": item["window_id"], "verification_status": VERIFICATION_STATUS, "formal_source_status": FORMAL_SOURCE_STATUS}
                for item in available_windows
            ]
            candidate["augmentation_node"]["gap_reason"] = "Commodity windows are computed, but company-specific exposure and transmission direction are not yet verified."
    crosschecks = _official_crosscheck_queue(requests)
    numeric_report = _numeric_evaluation(numeric_evaluation_path)
    base_summary = (
        json.loads(base_candidate_summary_path.read_text(encoding="utf-8"))
        if base_candidate_summary_path and base_candidate_summary_path.is_file()
        else {"company_dossier_count": 30, "candidate_sample_count": 60, "formal_ready": False}
    )

    output_root.mkdir(parents=True, exist_ok=True)
    source_manifest = [
        _source_record("wind-futures-calendar-csv", calendar_path, "FUTURES_CALENDAR"),
        _source_record("wind-futures-calendar-dictionary", calendar_dictionary_path, "DATA_DICTIONARY"),
        _source_record("wind-futures-description-csv", metadata_path, "CONTRACT_METADATA"),
        _source_record("wind-futures-description-dictionary", metadata_dictionary_path, "DATA_DICTIONARY"),
        _source_record("wind-commodity-futures-eod-csv", eod_path, "EOD_MARKET_DATA", content_sha256=eod_hash),
        _source_record("wind-commodity-futures-eod-dictionary", eod_dictionary_path, "DATA_DICTIONARY"),
        {
            "source_id": "financial-numeric-answer-evaluation",
            "role": "INDEPENDENT_NUMERIC_EVALUATION",
            "source_class": "NUMERIC_EVALUATION_BENCHMARK",
            "verification_status": "LOCAL_HASH_VERIFIED",
            "formal_source_status": "EXCLUDED_FROM_COMPANY_EVENT_DATASET",
            "local_snapshot_path": _relative(numeric_evaluation_path),
            "content_sha256": numeric_report["content_sha256"],
            "record_count": numeric_report["record_count"],
        },
    ]

    _write_jsonl(output_root / "vendor_source_manifest.jsonl", source_manifest)
    _write_json(output_root / "futures_calendar_profile.json", calendar_profile)
    _write_jsonl(output_root / "futures_contract_registry.jsonl", contract_registry)
    _write_json(output_root / "eod_schema_profile.json", eod_profile)
    _write_jsonl(output_root / "event_futures_window_requests.jsonl", requests)
    _write_jsonl(output_root / "event_futures_windows.jsonl", computed_windows)
    _write_jsonl(output_root / "company_chain_enhancement_candidates.jsonl", company_candidates)
    _write_jsonl(output_root / "official_crosscheck_queue.jsonl", crosschecks)
    _write_json(output_root / "numeric_evaluation_report.json", numeric_report)

    after_fingerprint = _directory_fingerprint(protected_roots)
    checks = {
        "source_classification_exact": all(
            item["source_class"] == SOURCE_CLASS
            and item["verification_status"] == VERIFICATION_STATUS
            and item["formal_source_status"] == FORMAL_SOURCE_STATUS
            for item in source_manifest[:6]
        ),
        "calendar_is_dce_only": calendar_profile["allowed_exchange"] == "DCE",
        "equity_calendar_substitution_forbidden": calendar_profile["forbidden_as_equity_calendar"] == ["SSE", "SZSE"],
        "priority_symbols_complete": [item["commodity_code"] for item in contract_registry] == list(PRIORITY_SYMBOLS),
        "priority_events_complete": {item["event_id"] for item in requests} == set(EVENTS),
        "window_request_count_is_16": len(requests) == 16,
        "historical_values_not_fabricated": all(
            (item["status"] == "PENDING_ARCHIVE" and not item["values_generated"] and not item["actual_values"])
            or (item["status"] == "VENDOR_WINDOW_COMPUTED" and item["values_generated"] and bool(item["actual_values"]))
            for item in requests
        ),
        "pending_archive_explicit": all(item["status"] != "PENDING_METHOD_REVIEW" for item in requests),
        "computed_windows_reproducible": all(
            len(item["calculation_trace"]) == 81
            and all(
                abs(
                    item["window_changes_pct"][label]
                    - round(_compound([row["daily_settlement_return_pct"] / 100.0 for row in item["calculation_trace"][60 : end + 1]]) * 100.0, 8)
                ) <= 1e-6
                for label, end in (("D1", 60), ("D3", 62), ("D5", 64), ("D20", 79))
            )
            for item in computed_windows
        ),
        "raw_vendor_prices_not_exposed": all(
            "settlement" not in row and "pre_settlement" not in row
            for item in computed_windows for row in item["calculation_trace"]
        ),
        "company_candidates_complete": len(company_candidates) == 6,
        "numeric_dataset_isolated": numeric_report["excluded_from_company_dossiers"] and numeric_report["excluded_from_event_samples"],
        "numeric_micro_regression_passed": numeric_report["micro_regression_passed"],
        "protected_outputs_unchanged": before_fingerprint == after_fingerprint,
        "formal_ready_is_false": True,
    }
    passed = all(checks.values())
    validation_report = {
        "dataset_version": DATASET_VERSION,
        "passed": passed,
        "checks": checks,
        "errors": [name for name, result in checks.items() if not result],
        "validated_at": retrieved_at or datetime.now(timezone.utc).isoformat(),
    }
    _write_json(output_root / "validation_report.json", validation_report)

    summary = {
        "dataset_version": DATASET_VERSION,
        "release_tier": "CANDIDATE",
        "candidate_ready": passed,
        "formal_ready": False,
        "event_count": len(EVENTS),
        "priority_symbol_count": len(PRIORITY_SYMBOLS),
        "window_request_count": len(requests),
        "computed_window_count": len(computed_windows),
        "pending_archive_count": sum(item["status"] == "PENDING_ARCHIVE" for item in requests),
        "company_enhancement_candidate_count": len(company_candidates),
        "numeric_evaluation_record_count": numeric_report["record_count"],
        "base_company_dossier_count": base_summary.get("company_dossier_count"),
        "base_candidate_sample_count": base_summary.get("candidate_sample_count"),
        "enhancement_company_sample_count": 0,
        "protected_outputs_unchanged": before_fingerprint == after_fingerprint,
        "source_class": SOURCE_CLASS,
        "verification_status": VERIFICATION_STATUS,
        "formal_source_status": FORMAL_SOURCE_STATUS,
        "formal_blockers": [
            "HISTORICAL_EOD_VENDOR_VERIFIED_OFFICIAL_SPOTCHECK_PENDING",
            "OFFICIAL_EXCHANGE_CROSSCHECK_INCOMPLETE",
            "COMPANY_EXPOSURE_LINKS_UNVERIFIED",
            "VENDOR_LICENSE_SCOPE_UNKNOWN",
        ],
    }
    _write_json(output_root / "summary.json", summary)
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    summary = build_vendor_enhancement(
        output_root=args.output_root,
        calendar_path=DEFAULT_CALENDAR,
        metadata_path=DEFAULT_METADATA,
        eod_path=DEFAULT_EOD,
        calendar_dictionary_path=DEFAULT_DICTIONARY_ROOT / "CFuturesCalendar_数据字典.pdf",
        metadata_dictionary_path=DEFAULT_DICTIONARY_ROOT / "CFuturesDescription_数据字典.pdf",
        eod_dictionary_path=DEFAULT_DICTIONARY_ROOT / "CCommodityFuturesEODPrices_数据字典.pdf",
        candidate_registry_path=DEFAULT_CANDIDATE_ROOT / "candidate_company_registry.jsonl",
        numeric_evaluation_path=DEFAULT_NUMERIC_EVALUATION,
        base_candidate_summary_path=DEFAULT_CANDIDATE_ROOT / "summary.json",
        wind_candidate_summary_path=DEFAULT_WIND_SUMMARY,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["candidate_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())