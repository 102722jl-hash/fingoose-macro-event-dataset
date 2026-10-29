"""Industry benchmark windows and optional reproducible market fetches."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from fingoose_company_impact_market_v2 import align_t0


WINDOW_OFFSETS = {
    "T_MINUS_1": -1,
    "T0": 0,
    "D1": 1,
    "D3": 3,
    "D5": 5,
    "D20": 20,
}


def normalized(value: float, base: float) -> float:
    if base == 0:
        raise ValueError("ZERO_BASE_VALUE")
    return value / base * 100.0


def excess_return(
    industry_start: float,
    industry_end: float,
    market_start: float,
    market_end: float,
) -> float:
    if industry_start == 0 or market_start == 0:
        raise ValueError("ZERO_BASE_VALUE")
    return (industry_end / industry_start - 1) - (
        market_end / market_start - 1
    )


def common_rows(
    industry_rows: Iterable[Mapping[str, Any]],
    market_rows: Iterable[Mapping[str, Any]],
) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    industry = {str(row["date"]): dict(row) for row in industry_rows}
    market = {str(row["date"]): dict(row) for row in market_rows}
    return [
        (day, industry[day], market[day])
        for day in sorted(set(industry) & set(market))
    ]


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    month_lengths = (31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    return date(year, month, min(value.day, month_lengths[month - 1]))


def _pending_window(mapping_id: str, reason: str) -> dict[str, Any]:
    return {
        "event_industry_mapping_id": mapping_id,
        "event_id": "event-01",
        "t0_alignment": None,
        "continuous_window": [],
        "fixed_windows": {},
        "driver_observations": [],
        "window_status": "DATA_PENDING",
        "pending_reason": reason,
        "review_status": "NEEDS_HUMAN_REVIEW",
        "formal_ready": False,
        "sha_gate": "DEFERRED",
    }


def build_industry_market_window(
    *,
    mapping_id: str,
    event_at: str,
    industry_rows: Iterable[Mapping[str, Any]],
    market_rows: Iterable[Mapping[str, Any]],
    driver_observations: Iterable[Mapping[str, Any]],
    market_timezone: str = "Asia/Shanghai",
) -> dict[str, Any]:
    rows = common_rows(industry_rows, market_rows)
    if not rows:
        return _pending_window(mapping_id, "NO_COMMON_TRADING_SESSIONS")
    sessions = [row[0] for row in rows]
    try:
        alignment = align_t0(
            event_at,
            sessions,
            market_timezone=market_timezone,
        )
    except ValueError as exc:
        return _pending_window(mapping_id, str(exc))
    t0_index = sessions.index(alignment["T0"])
    if t0_index < 20:
        return _pending_window(mapping_id, "INSUFFICIENT_T_MINUS_20_SESSIONS")
    if t0_index + 20 >= len(rows):
        return _pending_window(mapping_id, "INSUFFICIENT_D20_SESSIONS")

    base_day, base_industry_row, base_market_row = rows[t0_index - 1]
    industry_base = float(base_industry_row["close"])
    market_base = float(base_market_row["close"])
    if industry_base == 0 or market_base == 0:
        return _pending_window(mapping_id, "ZERO_T_MINUS_1_BASE")

    fixed: dict[str, dict[str, Any]] = {}
    for key, offset in WINDOW_OFFSETS.items():
        target_index = t0_index + offset
        day, industry_row, market_row = rows[target_index]
        industry_value = float(industry_row["close"])
        market_value = float(market_row["close"])
        industry_return = industry_value / industry_base - 1
        market_return = market_value / market_base - 1
        fixed[key] = {
            "actual_date": day,
            "industry_value": industry_value,
            "market_value": market_value,
            "industry_normalized": normalized(industry_value, industry_base),
            "market_normalized": normalized(market_value, market_base),
            "industry_return": industry_return,
            "market_return": market_return,
            "market_relative_return": industry_return - market_return,
            "formula": "(industry_value / industry_T_MINUS_1 - 1) - (market_value / market_T_MINUS_1 - 1)",
            "formula_inputs": {
                "industry_T_MINUS_1": industry_base,
                "industry_value": industry_value,
                "market_T_MINUS_1": market_base,
                "market_value": market_value,
            },
        }

    target_m3 = _add_months(date.fromisoformat(alignment["T0"]), 3)
    m3_candidates = [index for index, day in enumerate(sessions) if date.fromisoformat(day) >= target_m3]
    if not m3_candidates:
        return _pending_window(mapping_id, "M3_SESSION_UNAVAILABLE")
    m3_index = m3_candidates[0]
    day, industry_row, market_row = rows[m3_index]
    industry_value = float(industry_row["close"])
    market_value = float(market_row["close"])
    industry_return = industry_value / industry_base - 1
    market_return = market_value / market_base - 1
    fixed["M3"] = {
        "actual_date": day,
        "industry_value": industry_value,
        "market_value": market_value,
        "industry_normalized": normalized(industry_value, industry_base),
        "market_normalized": normalized(market_value, market_base),
        "industry_return": industry_return,
        "market_return": market_return,
        "market_relative_return": industry_return - market_return,
        "formula": "(industry_value / industry_T_MINUS_1 - 1) - (market_value / market_T_MINUS_1 - 1)",
        "formula_inputs": {
            "industry_T_MINUS_1": industry_base,
            "industry_value": industry_value,
            "market_T_MINUS_1": market_base,
            "market_value": market_value,
        },
    }

    continuous = []
    for day, industry_row, market_row in rows[t0_index - 20 : t0_index + 21]:
        industry_value = float(industry_row["close"])
        market_value = float(market_row["close"])
        continuous.append(
            {
                "actual_date": day,
                "industry_value": industry_value,
                "market_value": market_value,
                "industry_normalized": normalized(industry_value, industry_base),
                "market_normalized": normalized(market_value, market_base),
                "industry_return": industry_value / industry_base - 1,
                "market_return": market_value / market_base - 1,
                "market_relative_return": excess_return(
                    industry_base, industry_value, market_base, market_value
                ),
            }
        )
    return {
        "event_industry_mapping_id": mapping_id,
        "event_id": "event-01",
        "t0_alignment": alignment,
        "base_window": {"key": "T_MINUS_1", "actual_date": base_day},
        "continuous_window": continuous,
        "fixed_windows": fixed,
        "driver_observations": [dict(row) for row in driver_observations],
        "window_status": "AVAILABLE",
        "pending_reason": None,
        "review_status": "NEEDS_HUMAN_REVIEW",
        "formal_ready": False,
        "sha_gate": "DEFERRED",
    }


def build_market_windows_for_mappings(
    *,
    mappings: Iterable[Mapping[str, Any]],
    industry_rows_by_code: Mapping[str, Iterable[Mapping[str, Any]]],
    market_rows: Iterable[Mapping[str, Any]],
    market_timezone: str = "Asia/Shanghai",
    driver_observations_by_mapping: Mapping[
        str, Iterable[Mapping[str, Any]]
    ] | None = None,
) -> list[dict[str, Any]]:
    """Compute windows for a frozen mapping pool without price-based selection."""

    drivers = driver_observations_by_mapping or {}
    market = [dict(row) for row in market_rows]
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for mapping in mappings:
        mapping_id = str(mapping["event_industry_mapping_id"])
        if mapping_id in seen:
            raise ValueError(f"DUPLICATE_EVENT_INDUSTRY_MAPPING:{mapping_id}")
        seen.add(mapping_id)
        event_id = str(mapping["event_id"])
        event_at = mapping.get("anchor_first_public_at")
        if not event_at:
            window = _pending_window(mapping_id, "ANCHOR_FIRST_PUBLIC_AT_MISSING")
        else:
            window = build_industry_market_window(
                mapping_id=mapping_id,
                event_at=str(event_at),
                industry_rows=industry_rows_by_code.get(str(mapping["sw1_id"]), []),
                market_rows=market,
                driver_observations=drivers.get(mapping_id, []),
                market_timezone=market_timezone,
            )
        window["event_id"] = event_id
        window["event_at"] = event_at
        window["event_at_basis"] = "ANCHOR_FIRST_PUBLIC_AT"
        window["benchmark"] = {
            "benchmark_id": f"SW1-{mapping['sw1_id']}",
            "benchmark_code": f"{mapping['sw1_id']}.SI",
            "classification_edition": mapping["classification_edition"],
        }
        window["market_benchmark"] = {
            "benchmark_id": "CSI300",
            "benchmark_code": "000300.SH",
        }
        window["missing_value_policy"] = "KEEP_NULL_NEVER_ZERO_IMPUTE"
        window["price_selection_used"] = False
        output.append(window)
    return output


def fetch_sw_history(ak_module, code: str, *, requests_module=None):
    if requests_module is None:
        import requests as requests_module

    original_get = requests_module.get

    def get_without_brotli(*args, **kwargs):
        headers = dict(kwargs.get("headers") or {})
        headers["Accept-Encoding"] = "gzip, deflate"
        kwargs["headers"] = headers
        return original_get(*args, **kwargs)

    requests_module.get = get_without_brotli
    try:
        return ak_module.index_hist_sw(symbol=code, period="day")
    finally:
        requests_module.get = original_get


def call_with_retries(operation, *, attempts: int = 3):
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    last_error = None
    for _ in range(attempts):
        try:
            return operation()
        except Exception as exc:
            last_error = exc
    assert last_error is not None
    raise last_error


def fetch_market_registry(registry: Mapping[str, Any], raw_root: Path) -> list[dict[str, Any]]:
    raw_root.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.now(timezone.utc).isoformat()
    records: list[dict[str, Any]] = []
    try:
        import akshare as ak
    except Exception as exc:
        return [
            {
                "series_id": "ALL",
                "fetch_status": "AKSHARE_UNAVAILABLE",
                "failure_reason": f"{type(exc).__name__}:{exc}",
                "fetched_at": fetched_at,
            }
        ]

    for item in registry["industry_benchmarks"]:
        code = str(item["code"])
        output = raw_root / f"sw_{code}.csv"
        try:
            frame = call_with_retries(
                lambda: fetch_sw_history(ak, code), attempts=3
            )
            if frame is None or frame.empty:
                raise ValueError("EMPTY_PROVIDER_RESPONSE")
            frame.to_csv(output, index=False, encoding="utf-8-sig")
            records.append(
                {
                    "series_id": code,
                    "provider": "AKSHARE_SWSRESEARCH",
                    "provider_function": "index_hist_sw",
                    "provider_parameters": {"symbol": code, "period": "day"},
                    "raw_columns": [str(value) for value in frame.columns],
                    "raw_path": output.as_posix(),
                    "fetch_status": "AVAILABLE",
                    "failure_reason": None,
                    "fetched_at": fetched_at,
                    "licence_status": "PUBLIC_REPRODUCIBLE_LICENSE_REVIEW_PENDING",
                }
            )
        except Exception as exc:
            records.append(
                {
                    "series_id": code,
                    "provider": "AKSHARE_SWSRESEARCH",
                    "fetch_status": "DATA_PENDING",
                    "failure_reason": f"{type(exc).__name__}:{exc}",
                    "fetched_at": fetched_at,
                }
            )
    benchmark = registry["market_benchmark"]
    date_range = registry["date_range"]
    start_date = str(date_range["start_date"])
    end_date = str(date_range["end_date"])
    output = raw_root / "csi300.csv"
    try:
        frame = call_with_retries(
            lambda: ak.stock_zh_index_daily_tx(
                symbol=str(benchmark["code"]),
                start_date=start_date,
                end_date=end_date,
            ),
            attempts=3,
        )
        if frame is None or frame.empty:
            raise ValueError("EMPTY_PROVIDER_RESPONSE")
        frame.to_csv(output, index=False, encoding="utf-8-sig")
        records.append(
            {
                "series_id": str(benchmark["benchmark_id"]),
                "provider": "AKSHARE_TENCENT",
                "provider_function": "stock_zh_index_daily_tx",
                "provider_parameters": {
                    "symbol": benchmark["code"],
                    "start_date": start_date,
                    "end_date": end_date,
                },
                "raw_columns": [str(value) for value in frame.columns],
                "raw_path": output.as_posix(),
                "fetch_status": "AVAILABLE",
                "failure_reason": None,
                "fetched_at": fetched_at,
                "licence_status": "PUBLIC_REPRODUCIBLE_LICENSE_REVIEW_PENDING",
            }
        )
    except Exception as exc:
        records.append(
            {
                "series_id": str(benchmark["benchmark_id"]),
                "provider": "AKSHARE_TENCENT",
                "fetch_status": "DATA_PENDING",
                "failure_reason": f"{type(exc).__name__}:{exc}",
                "fetched_at": fetched_at,
            }
        )
    (raw_root / "market_fetch_manifest.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in records),
        encoding="utf-8",
    )
    return records


def load_market_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    output = []
    for row in rows:
        day = row.get("date") or row.get("日期") or row.get("day")
        close = row.get("close") or row.get("收盘") or row.get("收盘价")
        if day not in (None, "") and close not in (None, ""):
            output.append({"date": str(day)[:10], "close": float(close)})
    return output


def load_market_windows_from_raw(
    *,
    mappings: Iterable[Mapping[str, Any]],
    registry: Mapping[str, Any],
    raw_root: Path,
    driver_observations_by_mapping: Mapping[
        str, Iterable[Mapping[str, Any]]
    ] | None = None,
) -> list[dict[str, Any]]:
    """Load registered raw CSV series and compute all mapping windows."""

    mapping_rows = [dict(row) for row in mappings]
    market_path = raw_root / "csi300.csv"
    market_rows = load_market_csv(market_path) if market_path.exists() else []
    registered_codes = {
        str(item["code"])
        for item in registry.get("industry_benchmarks", [])
    }
    industry_rows_by_code: dict[str, list[dict[str, Any]]] = {}
    for code in sorted(registered_codes):
        industry_path = raw_root / f"sw_{code}.csv"
        if industry_path.exists():
            industry_rows_by_code[code] = load_market_csv(industry_path)
    return build_market_windows_for_mappings(
        mappings=mapping_rows,
        industry_rows_by_code=industry_rows_by_code,
        market_rows=market_rows,
        market_timezone=str(registry.get("market_timezone", "Asia/Shanghai")),
        driver_observations_by_mapping=driver_observations_by_mapping,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    registry_path = args.registry if args.registry.is_absolute() else root / args.registry
    output = args.output if args.output.is_absolute() else root / args.output
    registry = json.loads(registry_path.read_text(encoding="utf-8-sig"))
    rows = fetch_market_registry(registry, output)
    print(json.dumps({"series_count": len(rows)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
