"""Add market comparability and causal boundaries to research content."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .causal_identification import classify_causal_identification
from .evidence_closure import build_milestone_evidence_aliases
from .market_enrichment import (
    WINDOW_KEYS,
    attach_industry_market_windows,
    build_industry_window_sw1_index,
    calculate_company_relative_windows,
    index_industry_windows,
    merge_existing_market_relative_windows,
    resolve_company_industry_window,
)
from .research_content_impl_003 import build_event_research_content as _build
from .research_content import select_task_content


def _mapping_rows(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        return [value]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [row for row in value if isinstance(row, Mapping)]
    return []


def _collect_confounders(company: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for record in _mapping_rows(company.get("confounders")):
        registered = _mapping_rows(record.get("registered_confounders"))
        if registered:
            result.extend(deepcopy(dict(row)) for row in registered)
        elif record.get("display_state") or record.get("argument_zh"):
            result.append(deepcopy(dict(record)))
    return result


def _collect_counterevidence(company: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    review = company.get("counterevidence_review") or {}
    if isinstance(review, Mapping):
        rows.extend(_mapping_rows(review.get("findings")))
    confounders = company.get("confounders") or {}
    if isinstance(confounders, Mapping):
        rows.extend(_mapping_rows(confounders.get("counterevidence")))
    unique: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        key = str(
            row.get("counterevidence_id")
            or row.get("evidence_id")
            or f"counterevidence-{index}"
        )
        unique.setdefault(key, deepcopy(dict(row)))
    return [unique[key] for key in sorted(unique)]


def _causal_gates(
    ui_company: Mapping[str, Any], company_content: Mapping[str, Any]
) -> dict[str, bool]:
    relative = company_content.get("relative_market_windows") or {}
    complete = all(
        isinstance(relative.get(name), Mapping)
        and relative[name].get("status") == "CALCULATED"
        for name in WINDOW_KEYS
    )
    market = ui_company.get("market_window") or {}
    suspension_alignment = str(
        market.get("suspension_alignment")
        if isinstance(market, Mapping)
        else ""
    ).upper()
    design = ui_company.get("causal_design") or {}
    if not isinstance(design, Mapping):
        design = {}
    return {
        "market_windows_complete": complete,
        "market_benchmark_complete": complete,
        "industry_benchmark_complete": complete,
        # Endpoint price observations and vendor trading flags are not an
        # official continuous suspension/resumption audit.
        "continuous_trading_verified": suspension_alignment
        == "VERIFIED_SUSPENSION_ALIGNMENT",
        "comparison_group_defined": design.get("comparison_group_defined") is True,
        "pretrend_passed": design.get("pretrend_passed") is True,
        "confounders_controlled": design.get("confounders_controlled") is True,
        "robustness_passed": design.get("robustness_passed") is True,
        "counterevidence_passed": design.get("counterevidence_passed") is True,
    }


def build_event_research_content(
    ui_event: Mapping[str, Any],
) -> dict[str, Any]:
    content = _build(ui_event)
    raw_industry_windows = [
        row
        for row in ui_event.get("industry_market_windows") or []
        if isinstance(row, Mapping)
    ]
    windows_by_mapping = index_industry_windows(raw_industry_windows)
    windows_by_sw1 = build_industry_window_sw1_index(
        list(windows_by_mapping.values())
    )
    content["industry_impacts"] = attach_industry_market_windows(
        content.get("industry_impacts") or [], raw_industry_windows
    )

    ui_company_by_mapping = {
        str(row.get("mapping_id")): row
        for row in ui_event.get("companies") or []
        if isinstance(row, Mapping) and row.get("mapping_id")
    }
    for company in content.get("company_impacts") or []:
        mapping_id = str(company.get("mapping_id") or "")
        ui_company = ui_company_by_mapping.get(mapping_id)
        if ui_company is None:
            raise ValueError(f"ui company missing mapping_id={mapping_id}")
        industry_window = resolve_company_industry_window(
            ui_company, windows_by_mapping, windows_by_sw1
        )
        company["market_window"] = deepcopy(ui_company.get("market_window") or {})
        comparable = calculate_company_relative_windows(
            company["market_window"], industry_window or {}
        )
        company["relative_market_windows"] = merge_existing_market_relative_windows(
            comparable, ui_company.get("relative_window") or {}
        )
        causal = classify_causal_identification(
            _causal_gates(ui_company, company),
            confounders=_collect_confounders(ui_company),
            counterevidence=_collect_counterevidence(ui_company),
        )
        company["causal_identification"] = causal
        company["causal_attribution_allowed"] = causal[
            "causal_attribution_allowed"
        ]

    content["milestone_evidence_aliases"] = build_milestone_evidence_aliases(
        [
            row
            for row in ui_event.get("timeline") or []
            if isinstance(row, Mapping)
        ]
    )
    return content


__all__ = ["build_event_research_content", "select_task_content"]
