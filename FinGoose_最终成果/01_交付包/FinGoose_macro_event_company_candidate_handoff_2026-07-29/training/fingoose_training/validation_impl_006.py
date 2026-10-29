"""Validate evidence closure, market arithmetic, and causal gates."""

from __future__ import annotations

from collections import Counter
from math import isfinite
from typing import Any, Mapping

from .validation_impl_005 import (
    _check as _check_v5,
    _error,
    validate_datasets as _validate_v5,
    validate_reasoning_chain,
)


CAUSAL_STATUSES = {
    "NOT_IDENTIFIED",
    "DESCRIPTIVE_EVENT_STUDY",
    "QUASI_EXPERIMENTAL_CANDIDATE",
    "IDENTIFIED",
}


def _check_causal(content: Mapping[str, Any], sample_id: Any) -> list[dict[str, str]]:
    causal = content.get("causal_identification")
    if not isinstance(causal, Mapping):
        return []
    status = str(causal.get("status") or "")
    allowed = causal.get("causal_attribution_allowed") is True
    conclusion = causal.get("causal_conclusion")
    gates = causal.get("gate_results") or {}
    all_gates_pass = bool(gates) and all(value is True for value in gates.values())
    contradiction = (
        status not in CAUSAL_STATUSES
        or (status != "IDENTIFIED" and (allowed or conclusion != "ABSTAIN"))
        or (status == "IDENTIFIED" and (not allowed or not all_gates_pass))
    )
    return (
        [_error("CAUSAL_GATE_CONTRADICTION", sample_id, status)]
        if contradiction
        else []
    )


def _number(value: Any) -> float:
    result = float(value)
    if not isfinite(result):
        raise ValueError("non-finite number")
    return result


def _mismatch(actual: Any, expected: float, tolerance: float) -> bool:
    try:
        return abs(_number(actual) - expected) > tolerance
    except (TypeError, ValueError):
        return True


def _endpoint_return(value: Any) -> float:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("endpoint pair required")
    start, end = _number(value[0]), _number(value[1])
    if start == 0:
        raise ZeroDivisionError
    return end / start - 1


def _check_market_calculations(
    content: Mapping[str, Any], sample_id: Any, tolerance: float = 1e-12
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    windows = content.get("relative_market_windows") or {}
    if not isinstance(windows, Mapping):
        return errors
    for name, raw_row in windows.items():
        row = raw_row if isinstance(raw_row, Mapping) else {}
        status = str(row.get("status") or "")
        if status == "DATA_MISSING":
            if not row.get("missing_reason"):
                errors.append(_error("MARKET_MISSING_REASON_REQUIRED", sample_id, name))
            continue
        if status not in {"CALCULATED", "PARTIAL_CALCULATED"}:
            errors.append(_error("MARKET_CALCULATION_MISMATCH", sample_id, name))
            continue
        inputs = row.get("formula_inputs") or {}
        if "company" in inputs or "market" in inputs:
            try:
                company_return = _endpoint_return(inputs["company"])
                market_return = _endpoint_return(inputs["market"])
            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                errors.append(_error("MARKET_CALCULATION_MISMATCH", sample_id, name))
                continue
            mismatch = any(
                (
                    _mismatch(row.get("company_absolute_return"), company_return, tolerance),
                    _mismatch(row.get("market_return"), market_return, tolerance),
                    _mismatch(
                        row.get("market_relative_return"),
                        company_return - market_return,
                        tolerance,
                    ),
                )
            )
            industry_pair = inputs.get("industry")
            has_industry = (
                isinstance(industry_pair, (list, tuple))
                and len(industry_pair) == 2
                and all(value is not None for value in industry_pair)
            )
            if has_industry:
                try:
                    industry_return = _endpoint_return(industry_pair)
                    mismatch = mismatch or _mismatch(
                        row.get("industry_return"), industry_return, tolerance
                    ) or _mismatch(
                        row.get("industry_relative_return"),
                        company_return - industry_return,
                        tolerance,
                    )
                except (TypeError, ValueError, ZeroDivisionError):
                    mismatch = True
            elif status == "CALCULATED":
                mismatch = True
            elif not row.get("missing_reason"):
                errors.append(
                    _error("MARKET_MISSING_REASON_REQUIRED", sample_id, name)
                )
            if mismatch:
                errors.append(_error("MARKET_CALCULATION_MISMATCH", sample_id, name))
            continue
        try:
            company_return = _number(inputs["company_absolute_return"])
            market_base = _number(inputs["market_base_value"])
            market_value = _number(inputs["market_value"])
            if market_base == 0:
                raise ZeroDivisionError
            expected_market = company_return - (market_value / market_base - 1)
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            errors.append(_error("MARKET_CALCULATION_MISMATCH", sample_id, name))
            continue
        mismatch = _mismatch(
            row.get("market_relative_return"), expected_market, tolerance
        )
        industry_inputs = all(
            inputs.get(key) is not None
            for key in ("industry_base_value", "industry_value")
        )
        if status == "CALCULATED" and not industry_inputs:
            mismatch = True
        if industry_inputs:
            try:
                industry_base = _number(inputs["industry_base_value"])
                industry_value = _number(inputs["industry_value"])
                if industry_base == 0:
                    raise ZeroDivisionError
                expected_industry = company_return - (
                    industry_value / industry_base - 1
                )
                mismatch = mismatch or _mismatch(
                    row.get("industry_relative_return"), expected_industry, tolerance
                )
            except (TypeError, ValueError, ZeroDivisionError):
                mismatch = True
        elif status == "PARTIAL_CALCULATED" and not row.get("missing_reason"):
            errors.append(_error("MARKET_MISSING_REASON_REQUIRED", sample_id, name))
        if mismatch:
            errors.append(_error("MARKET_CALCULATION_MISMATCH", sample_id, name))
    return errors


def _closure_reason_stats(sft_samples: list[Mapping[str, Any]]) -> dict[str, int]:
    stats: Counter[str] = Counter()
    for sample in sft_samples:
        gate = (
            ((sample.get("metadata") or {}).get("reasoning_chain") or {}).get(
                "closure_gate"
            )
            or {}
        )
        if gate.get("status") == "CLOSED":
            stats["CLOSED"] += 1
            continue
        for blocker in gate.get("blockers") or ["UNKNOWN_OPEN_REASON"]:
            reason = str(blocker).split(":", 1)[0]
            normalized = (
                "SOURCE_EVIDENCE_INCOMPLETE"
                if reason == "EVIDENCE_MISSING"
                else reason
            )
            stats[normalized] += 1
    return dict(sorted(stats.items()))


def _market_completeness_stats(
    sft_samples: list[Mapping[str, Any]],
) -> dict[str, int]:
    industries = [
        row for row in sft_samples if row.get("task_type") == "INDUSTRY_IMPACT"
    ]
    companies = [
        row for row in sft_samples if row.get("task_type") == "COMPANY_IMPACT"
    ]
    statuses: Counter[str] = Counter()
    for sample in companies:
        content = (sample.get("metadata") or {}).get("research_content") or {}
        for window in (content.get("relative_market_windows") or {}).values():
            if isinstance(window, Mapping):
                statuses[str(window.get("status") or "UNKNOWN")] += 1
    return {
        "industry_total": len(industries),
        "company_total": len(companies),
        "company_calculated_window_count": statuses["CALCULATED"],
        "company_partial_window_count": statuses["PARTIAL_CALCULATED"],
        "company_missing_window_count": statuses["DATA_MISSING"],
    }


def _causal_status_stats(
    sft_samples: list[Mapping[str, Any]],
) -> dict[str, int]:
    stats: Counter[str] = Counter({status: 0 for status in CAUSAL_STATUSES})
    for sample in sft_samples:
        if sample.get("task_type") != "COMPANY_IMPACT":
            continue
        content = (sample.get("metadata") or {}).get("research_content") or {}
        status = str(
            (content.get("causal_identification") or {}).get("status")
            or "NOT_IDENTIFIED"
        )
        stats[status] += 1
    return dict(sorted(stats.items()))


def _check(sample: Mapping[str, Any]) -> list[dict[str, str]]:
    errors = list(_check_v5(sample))
    metadata = sample.get("metadata") or {}
    content = metadata.get("research_content") or {}
    sample_id = sample.get("sample_id")
    errors.extend(_check_causal(content, sample_id))
    errors.extend(_check_market_calculations(content, sample_id))

    graph = metadata.get("reasoning_chain") or {}
    registry = {
        str(row.get("evidence_id")): row
        for row in metadata.get("evidence_registry") or []
        if isinstance(row, Mapping) and row.get("evidence_id")
    }
    for node in graph.get("nodes") or []:
        if not isinstance(node, Mapping) or node.get("node_type") != "EVENT_FACT":
            continue
        for evidence_id in node.get("evidence_ids") or []:
            if str(evidence_id) not in registry:
                errors.append(_error("REGISTRY_NOT_INHERITED", sample_id, evidence_id))

    aliases = content.get("milestone_evidence_aliases") or {}
    node_by_id = {
        str(row.get("node_id")): row
        for row in graph.get("nodes") or []
        if isinstance(row, Mapping) and row.get("node_id")
    }
    for node_id, evidence_ids in aliases.items():
        node = node_by_id.get(str(node_id))
        if node is not None and not set(evidence_ids) <= set(
            node.get("evidence_ids") or []
        ):
            errors.append(_error("ALIAS_UNRESOLVED", sample_id, node_id))
    return errors


def validate_datasets(
    unified_events,
    sft_samples,
    expected_events,
    expected_task_types=None,
):
    report = _validate_v5(
        unified_events, sft_samples, expected_events, expected_task_types
    )
    extra = [
        error
        for sample in sft_samples
        for error in _check(sample)
        if error not in report.get("errors", [])
    ]
    report["errors"] = list(report.get("errors") or []) + extra
    report["valid"] = not report["errors"]
    report["closure_reason_stats"] = _closure_reason_stats(sft_samples)
    report["market_completeness_stats"] = _market_completeness_stats(sft_samples)
    report["causal_identification_stats"] = _causal_status_stats(sft_samples)
    return report


__all__ = ["validate_datasets", "validate_reasoning_chain"]
