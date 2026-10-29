"""Market-session alignment and relative-return calculations for company impact v2."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo


MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(15, 0)


def align_t0(
    event_at: str,
    sessions: Iterable[str],
    *,
    market_timezone: str = "Asia/Shanghai",
) -> dict[str, str]:
    ordered = sorted({date.fromisoformat(value) for value in sessions})
    if not ordered:
        raise ValueError("EMPTY_SESSION_CALENDAR")
    if len(event_at) == 10:
        local_date = date.fromisoformat(event_at)
        local_text = event_at
        local_clock = None
        after_close = False
    else:
        parsed = datetime.fromisoformat(event_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("EVENT_TIMEZONE_REQUIRED")
        local = parsed.astimezone(ZoneInfo(market_timezone))
        local_date = local.date()
        local_text = local.isoformat()
        local_clock = local.timetz().replace(tzinfo=None)
        after_close = local_clock > MARKET_CLOSE
    if local_date in ordered and not after_close:
        t0 = local_date
        if len(event_at) == 10:
            reason = "DATE_PRECISION_SAME_OR_NEXT_SESSION"
        elif local_clock is not None and local_clock < MARKET_OPEN:
            reason = "PRE_OPEN_SAME_SESSION"
        else:
            reason = "IN_SESSION_SAME_DAY"
    else:
        candidates = [session for session in ordered if session > local_date]
        if not candidates:
            raise ValueError("NO_SESSION_AFTER_EVENT")
        t0 = candidates[0]
        reason = "AFTER_CLOSE_NEXT_SESSION" if after_close else "NON_SESSION_NEXT_SESSION"
    return {
        "T0": t0.isoformat(),
        "alignment_reason": reason,
        "local_event_at": local_text,
    }


def relative_return(
    *,
    company: tuple[float, float],
    benchmark: tuple[float, float],
) -> float:
    company_start, company_end = company
    benchmark_start, benchmark_end = benchmark
    if company_start == 0 or benchmark_start == 0:
        raise ValueError("ZERO_BASE_VALUE")
    return (company_end / company_start - 1) - (
        benchmark_end / benchmark_start - 1
    )


def _validate_dates(
    company_window: Mapping[str, Any],
    comparison_window: Mapping[str, Any],
) -> None:
    if (
        company_window["start_date"] != comparison_window["start_date"]
        or company_window["end_date"] != comparison_window["end_date"]
    ):
        raise ValueError("WINDOW_DATE_MISMATCH")


def build_relative_window(
    company_window: Mapping[str, Any],
    market_window: Mapping[str, Any],
    industry_window: Mapping[str, Any] | None,
) -> dict[str, Any]:
    _validate_dates(company_window, market_window)
    company_values = (
        float(company_window["start_value"]),
        float(company_window["end_value"]),
    )
    market_values = (
        float(market_window["start_value"]),
        float(market_window["end_value"]),
    )
    company_return = company_values[1] / company_values[0] - 1
    market_return = market_values[1] / market_values[0] - 1
    result = {
        "start_date": company_window["start_date"],
        "end_date": company_window["end_date"],
        "company_return": company_return,
        "market_return": market_return,
        "market_relative_return": relative_return(
            company=company_values,
            benchmark=market_values,
        ),
        "industry_relative_return": None,
        "industry_status": "DATA_PENDING",
        "formula": "company_end/company_start-1 - benchmark_end/benchmark_start+1",
    }
    if industry_window is not None:
        _validate_dates(company_window, industry_window)
        industry_values = (
            float(industry_window["start_value"]),
            float(industry_window["end_value"]),
        )
        result["industry_relative_return"] = relative_return(
            company=company_values,
            benchmark=industry_values,
        )
        result["industry_status"] = str(
            industry_window.get("benchmark_type", "AVAILABLE")
        )
    return result


def _observed_close(observation: Mapping[str, Any] | None) -> float | None:
    if not observation or observation.get("status") != "OBSERVED":
        return None
    value = observation.get("close")
    if value is None:
        return None
    return float(value)


def build_relative_record(
    company_window: Mapping[str, Any],
    market_bars: Mapping[str, Mapping[str, Any]],
    *,
    market_benchmark_id: str,
    industry_bars: Mapping[str, Mapping[str, Any]] | None,
    industry_benchmark_id: str | None,
) -> dict[str, Any]:
    observations = company_window.get("observations")
    if not isinstance(observations, Mapping):
        raise ValueError("COMPANY_OBSERVATIONS_REQUIRED")
    baseline = observations.get("T_MINUS_1")
    if not isinstance(baseline, Mapping):
        raise ValueError("T_MINUS_1_REQUIRED")
    start_date = baseline.get("date")
    company_start = _observed_close(baseline)
    if not start_date or company_start is None:
        raise ValueError("OBSERVED_T_MINUS_1_REQUIRED")

    output_observations: dict[str, dict[str, Any]] = {}
    for horizon, raw_observation in observations.items():
        observation = raw_observation if isinstance(raw_observation, Mapping) else {}
        end_date = observation.get("date")
        company_end = _observed_close(observation)
        result = {
            "start_date": start_date,
            "end_date": end_date,
            "company_return": None,
            "market_return": None,
            "market_relative_return": None,
            "market_status": "DATA_PENDING",
            "industry_relative_return": None,
            "industry_status": "DATA_PENDING",
            "formula": "(company_end/company_start-1) - (benchmark_end/benchmark_start-1)",
            "formula_inputs": {
                "company": [company_start, company_end],
                "market": [None, None],
                "industry": [None, None],
            },
            "gap_reason": None,
        }
        if company_end is None or not end_date:
            result["gap_reason"] = "COMPANY_END_OBSERVATION_MISSING"
            output_observations[str(horizon)] = result
            continue

        result["company_return"] = company_end / company_start - 1
        market_start_row = market_bars.get(str(start_date))
        market_end_row = market_bars.get(str(end_date))
        market_start = _observed_close(
            {"status": "OBSERVED", "close": market_start_row.get("close")}
            if market_start_row
            else None
        )
        market_end = _observed_close(
            {"status": "OBSERVED", "close": market_end_row.get("close")}
            if market_end_row
            else None
        )
        result["formula_inputs"]["market"] = [market_start, market_end]
        if market_start is None:
            result["gap_reason"] = "MARKET_START_DATE_MISSING"
        elif market_end is None:
            result["gap_reason"] = "MARKET_END_DATE_MISSING"
        else:
            result["market_return"] = market_end / market_start - 1
            result["market_relative_return"] = relative_return(
                company=(company_start, company_end),
                benchmark=(market_start, market_end),
            )
            result["market_status"] = "AVAILABLE"

        if industry_bars is not None and industry_benchmark_id is not None:
            industry_start_row = industry_bars.get(str(start_date))
            industry_end_row = industry_bars.get(str(end_date))
            industry_start = _observed_close(
                {"status": "OBSERVED", "close": industry_start_row.get("close")}
                if industry_start_row
                else None
            )
            industry_end = _observed_close(
                {"status": "OBSERVED", "close": industry_end_row.get("close")}
                if industry_end_row
                else None
            )
            result["formula_inputs"]["industry"] = [industry_start, industry_end]
            if industry_start is not None and industry_end is not None:
                result["industry_relative_return"] = relative_return(
                    company=(company_start, company_end),
                    benchmark=(industry_start, industry_end),
                )
                result["industry_status"] = "AVAILABLE"
        output_observations[str(horizon)] = result

    return {
        "relative_window_id": f"relative-{company_window['price_window_id']}",
        "price_window_id": company_window["price_window_id"],
        "event_id": company_window["event_id"],
        "anchor_id": company_window.get("anchor_id"),
        "company_code": company_window["company_code"],
        "adjustment": company_window.get("adjustment"),
        "market_benchmark_id": market_benchmark_id,
        "industry_benchmark_id": industry_benchmark_id,
        "observations": output_observations,
        "formal_ready": False,
    }


def build_market_outputs(
    company_windows: Iterable[Mapping[str, Any]],
    mappings: Iterable[Mapping[str, Any]],
    market_bars: Mapping[str, Mapping[str, Any]],
    *,
    market_benchmark_id: str = "CSI300",
) -> dict[str, Any]:
    windows_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for raw_window in company_windows:
        window = dict(raw_window)
        key = (str(window.get("event_id")), str(window.get("company_code")))
        windows_by_key.setdefault(key, []).append(window)

    hard_failures: list[str] = []
    company_market_windows: list[dict[str, Any]] = []
    relative_return_windows: list[dict[str, Any]] = []
    source_registry: list[dict[str, Any]] = []
    for raw_mapping in mappings:
        mapping = dict(raw_mapping)
        mapping_id = str(mapping.get("mapping_id"))
        key = (str(mapping.get("event_id")), str(mapping.get("company_code")))
        matches = windows_by_key.get(key, [])
        if len(matches) != 1:
            hard_failures.append(f"WINDOW_CARDINALITY_MISMATCH:{mapping_id}")
            continue
        source = matches[0]
        if source.get("anchor_id") != mapping.get("anchor_id"):
            hard_failures.append(f"WINDOW_LINEAGE_MISMATCH:{mapping_id}")
            continue

        projected_observations: dict[str, dict[str, Any]] = {}
        for horizon, raw_observation in source.get("observations", {}).items():
            observation = dict(raw_observation)
            close = observation.get("close")
            projected_observations[str(horizon)] = {
                "target_session_offset": observation.get("trading_session_offset"),
                "actual_date": observation.get("date"),
                "raw_close": None,
                "forward_adjusted_close": close,
                "absolute_return": observation.get(
                    "absolute_return", observation.get("raw_return_from_t_minus_1")
                ),
                "status": observation.get("status"),
                "raw_close_gap_reason": "SOURCE_PROVIDED_FORWARD_ADJUSTED_CLOSE_ONLY",
            }
        market_row = {
            "company_market_window_id": f"company-market-{mapping_id}",
            "mapping_id": mapping_id,
            "company_id": mapping.get("company_id"),
            "event_id": mapping.get("event_id"),
            "anchor_id": mapping.get("anchor_id"),
            "company_code": mapping.get("company_code"),
            "company_name": source.get("company_name"),
            "source_price_window_id": source.get("price_window_id"),
            "frequency": source.get("frequency", "DAILY"),
            "adjustment": source.get("adjustment"),
            "calendar_alignment": source.get("calendar_alignment"),
            "suspension_alignment": source.get("suspension_alignment", "UNVERIFIED"),
            "market_benchmark_id": market_benchmark_id,
            "industry_benchmark_id": None,
            "industry_benchmark_status": "DATA_PENDING",
            "observations": projected_observations,
            "formal_ready": False,
            "causal_attribution_allowed": False,
        }
        relative_row = build_relative_record(
            source,
            market_bars,
            market_benchmark_id=market_benchmark_id,
            industry_bars=None,
            industry_benchmark_id=None,
        )
        relative_row.update(
            {
                "mapping_id": mapping_id,
                "company_id": mapping.get("company_id"),
                "industry_id": mapping.get("industry_classification", {}).get("sw1_id"),
                "causal_attribution_allowed": False,
            }
        )
        company_market_windows.append(market_row)
        relative_return_windows.append(relative_row)
        source_registry.append(
            {
                "source_record_id": f"market-source-{source.get('price_window_id')}",
                "source_type": "COMPANY_PRICE_WINDOW",
                "price_window_id": source.get("price_window_id"),
                "provider": source.get("source_provider"),
                "source_url": source.get("source_url"),
                "snapshot_path": source.get("snapshot_path"),
                "snapshot_sha256": source.get("source_snapshot_sha256"),
                "adjustment": source.get("adjustment"),
                "redistribution_allowed": source.get("redistribution_allowed", False),
                "formal_ready": False,
            }
        )

    return {
        "company_market_windows": sorted(
            company_market_windows, key=lambda row: str(row["mapping_id"])
        ),
        "relative_return_windows": sorted(
            relative_return_windows, key=lambda row: str(row["mapping_id"])
        ),
        "market_source_registry": sorted(
            source_registry, key=lambda row: str(row["source_record_id"])
        ),
        "validation": {
            "hard_failures": sorted(hard_failures),
            "company_window_count": len(company_market_windows),
            "relative_window_count": len(relative_return_windows),
            "market_benchmark_id": market_benchmark_id,
            "industry_benchmark_status": "DATA_PENDING",
            "formal_ready": False,
            "sha_gate": "DEFERRED",
        },
    }
