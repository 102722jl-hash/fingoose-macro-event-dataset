"""Deterministic industry-window linking and comparable company returns."""

from __future__ import annotations

from copy import deepcopy
import math
from typing import Any, Mapping, Sequence


WINDOW_KEYS = ("T0", "D1", "D3", "D5", "D20")


class MarketEnrichmentError(ValueError):
    """Raised when market-window mappings are ambiguous or malformed."""


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def index_industry_windows(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        mapping_id = _text(row.get("event_industry_mapping_id"))
        if not mapping_id:
            raise MarketEnrichmentError("industry window missing mapping_id")
        if mapping_id in result:
            raise MarketEnrichmentError(f"duplicate industry window: {mapping_id}")
        result[mapping_id] = deepcopy(dict(row))
    return result


def attach_industry_market_windows(
    industry_impacts: Sequence[Mapping[str, Any]],
    industry_market_windows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    windows = index_industry_windows(industry_market_windows)
    result: list[dict[str, Any]] = []
    for impact in industry_impacts:
        clean = deepcopy(dict(impact))
        mapping_id = _text(clean.get("event_industry_mapping_id"))
        if mapping_id not in windows:
            raise MarketEnrichmentError(
                f"industry market window missing: {mapping_id or '<empty>'}"
            )
        clean["market_window"] = deepcopy(windows[mapping_id])
        result.append(clean)
    return result


def _sw1_id(row: Mapping[str, Any]) -> str:
    direct = _text(row.get("sw1_id") or row.get("industry_id"))
    if direct:
        return direct
    benchmark = row.get("benchmark") or {}
    benchmark_id = _text(
        benchmark.get("benchmark_id") if isinstance(benchmark, Mapping) else None
    )
    return benchmark_id.split("-", 1)[1] if benchmark_id.startswith("SW1-") else ""


def build_industry_window_sw1_index(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        sw1_id = _sw1_id(row)
        if not sw1_id:
            continue
        if sw1_id in result:
            raise MarketEnrichmentError(f"duplicate industry sw1 window: {sw1_id}")
        result[sw1_id] = deepcopy(dict(row))
    return result


def resolve_company_industry_window(
    company: Mapping[str, Any],
    windows_by_mapping: Mapping[str, Mapping[str, Any]],
    windows_by_sw1: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any] | None:
    binding = company.get("binding_review") or {}
    mapping_id = _text(
        (binding.get("industry_impact_id") if isinstance(binding, Mapping) else None)
        or company.get("industry_impact_id")
    )
    if mapping_id and mapping_id in windows_by_mapping:
        return deepcopy(dict(windows_by_mapping[mapping_id]))
    market = company.get("market_window") or {}
    sw1_id = _text(
        market.get("industry_id") if isinstance(market, Mapping) else None
    )
    if sw1_id and sw1_id in windows_by_sw1:
        return deepcopy(dict(windows_by_sw1[sw1_id]))
    if mapping_id:
        raise MarketEnrichmentError(
            f"company industry mapping window missing: {mapping_id}"
        )
    if not sw1_id:
        return None
    raise MarketEnrichmentError(f"company industry sw1 window missing: {sw1_id}")


def _missing(reason: str) -> dict[str, str]:
    return {"status": "DATA_MISSING", "missing_reason": reason}


def calculate_company_relative_windows(
    company_window: Mapping[str, Any],
    industry_window: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    observations = company_window.get("observations") or {}
    if not isinstance(observations, Mapping):
        observations = {}
    base = observations.get("T_MINUS_1") or {}
    base_date = _text(base.get("actual_date") if isinstance(base, Mapping) else None)

    by_date: dict[str, Mapping[str, Any]] = {}
    for row in industry_window.get("continuous_window") or []:
        if not isinstance(row, Mapping):
            continue
        actual_date = _text(row.get("actual_date"))
        if not actual_date:
            continue
        if actual_date in by_date:
            raise MarketEnrichmentError(
                f"duplicate benchmark actual_date: {actual_date}"
            )
        by_date[actual_date] = row

    result: dict[str, dict[str, Any]] = {}
    for name in WINDOW_KEYS:
        observation = observations.get(name) or {}
        if not isinstance(observation, Mapping):
            observation = {}
        actual_date = _text(observation.get("actual_date"))
        if not actual_date:
            result[name] = _missing(f"COMPANY_WINDOW_MISSING:{name}")
            continue
        if not base_date or base_date not in by_date:
            result[name] = _missing(
                f"BENCHMARK_BASE_DATE_NOT_FOUND:{base_date or 'UNKNOWN'}"
            )
            continue
        if actual_date not in by_date:
            result[name] = _missing(
                f"BENCHMARK_ACTUAL_DATE_NOT_FOUND:{actual_date}"
            )
            continue

        base_row = by_date[base_date]
        target_row = by_date[actual_date]
        company_return = _number(observation.get("absolute_return"))
        industry_base = _number(base_row.get("industry_value"))
        industry_value = _number(target_row.get("industry_value"))
        market_base = _number(base_row.get("market_value"))
        market_value = _number(target_row.get("market_value"))
        if any(
            value is None
            for value in (
                company_return,
                industry_base,
                industry_value,
                market_base,
                market_value,
            )
        ):
            result[name] = _missing(f"FORMULA_INPUT_MISSING:{name}")
            continue
        if industry_base == 0.0 or market_base == 0.0:
            result[name] = _missing(f"BENCHMARK_BASE_ZERO:{name}")
            continue

        industry_return = industry_value / industry_base - 1.0
        market_return = market_value / market_base - 1.0
        result[name] = {
            "status": "CALCULATED",
            "actual_date": actual_date,
            "formula_version": "company-relative-v1",
            "formula_inputs": {
                "company_absolute_return": company_return,
                "industry_base_value": industry_base,
                "industry_value": industry_value,
                "market_base_value": market_base,
                "market_value": market_value,
            },
            "industry_return": industry_return,
            "market_return": market_return,
            "industry_relative_return": company_return - industry_return,
            "market_relative_return": company_return - market_return,
        }
    return result


def merge_existing_market_relative_windows(
    calculated_windows: Mapping[str, Mapping[str, Any]],
    existing_relative_window: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Fill a missing CSI300 comparison without inventing an industry return."""

    result = {
        str(name): deepcopy(dict(row))
        for name, row in calculated_windows.items()
        if isinstance(row, Mapping)
    }
    observations = existing_relative_window.get("observations") or {}
    if not isinstance(observations, Mapping):
        return result
    for name, current in result.items():
        if current.get("status") != "DATA_MISSING":
            continue
        source = observations.get(name) or {}
        if not isinstance(source, Mapping):
            continue
        company_return = _number(source.get("company_return"))
        market_return = _number(source.get("market_return"))
        market_relative = _number(source.get("market_relative_return"))
        if (
            str(source.get("market_status") or "").upper() != "AVAILABLE"
            or company_return is None
            or market_return is None
            or market_relative is None
        ):
            continue
        industry_return = _number(source.get("industry_return"))
        industry_relative = _number(source.get("industry_relative_return"))
        industry_available = (
            str(source.get("industry_status") or "").upper() == "AVAILABLE"
            and industry_return is not None
            and industry_relative is not None
        )
        result[name] = {
            "status": "CALCULATED" if industry_available else "PARTIAL_CALCULATED",
            "actual_date": source.get("end_date") or source.get("actual_date"),
            "formula_version": "company-relative-source-v1",
            "formula": source.get("formula"),
            "formula_inputs": deepcopy(source.get("formula_inputs") or {}),
            "company_absolute_return": company_return,
            "market_return": market_return,
            "market_relative_return": market_relative,
            "industry_return": industry_return,
            "industry_relative_return": industry_relative,
        }
        if not industry_available:
            result[name]["missing_reason"] = "INDUSTRY_BENCHMARK_DATA_PENDING"
    return result


__all__ = [
    "WINDOW_KEYS",
    "MarketEnrichmentError",
    "attach_industry_market_windows",
    "build_industry_window_sw1_index",
    "calculate_company_relative_windows",
    "index_industry_windows",
    "merge_existing_market_relative_windows",
    "resolve_company_industry_window",
]
