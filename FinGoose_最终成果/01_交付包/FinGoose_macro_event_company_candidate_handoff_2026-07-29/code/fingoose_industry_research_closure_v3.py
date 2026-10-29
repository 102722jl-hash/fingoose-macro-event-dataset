"""Build industry evidence closure, event studies, and company linkage matrices."""

from __future__ import annotations

import math
import statistics
from typing import Any, Mapping, MutableMapping, Sequence


WINDOW_RANGES = {
    "PRETREND": (-20, -2),
    "EVENT": (0, 1),
    "SHORT": (2, 5),
    "MEDIUM": (6, 20),
}

STATUS_ZH = {
    "VERIFIED_SOURCE": "原文已定位",
    "SUPPORTED_INFERENCE": "有前提支持的研究推断",
    "INFERENCE_ONLY": "研究推断，尚无直接证据",
    "EVIDENCE_MISSING": "证据缺口",
}


def _round(value: float | None, digits: int = 6) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(float(value), digits)


def _direction(value: float, threshold: float = 0.001) -> str:
    if value > threshold:
        return "POSITIVE"
    if value < -threshold:
        return "NEGATIVE"
    return "FLAT"


def _evidence_row(evidence_id: str, evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source = evidence or {}
    return {
        "evidence_id": evidence_id,
        "missing": not bool(evidence),
        "title": source.get("title") or source.get("document_title"),
        "publisher": source.get("publisher") or source.get("issuer"),
        "source_tier": source.get("source_tier"),
        "first_public_at": source.get("first_public_at") or source.get("published_at"),
        "original_quote": source.get("original_quote"),
        "locator": source.get("locator") or source.get("page_or_section_locator"),
        "source_url": source.get("source_url"),
        "snapshot_sha256": source.get("snapshot_sha256") or source.get("source_snapshot_sha256"),
        "supports_steps": [],
    }


def build_research_closure(impact: Mapping[str, Any]) -> dict[str, Any]:
    nodes = list((impact.get("mechanism_chain") or {}).get("nodes") or [])
    registry: dict[str, dict[str, Any]] = {}
    node_statuses: list[dict[str, Any]] = []
    supported_steps: set[int] = set()

    for step, node in enumerate(nodes, start=1):
        evidence_by_id = {
            str(row.get("evidence_id")): row
            for row in node.get("evidence") or []
            if row.get("evidence_id")
        }
        evidence_ids = [str(value) for value in node.get("evidence_ids") or []]
        missing_ids = [str(value) for value in node.get("missing_evidence_ids") or []]
        for evidence_id in evidence_ids:
            candidate = _evidence_row(evidence_id, evidence_by_id.get(evidence_id))
            current = registry.setdefault(evidence_id, candidate)
            if current["missing"] and not candidate["missing"]:
                candidate["supports_steps"] = current["supports_steps"]
                registry[evidence_id] = current = candidate
            if step not in current["supports_steps"]:
                current["supports_steps"].append(step)

        if missing_ids or (evidence_ids and not evidence_by_id):
            status = "EVIDENCE_MISSING"
            boundary = "已登记证据 ID，但当前候选包没有可核对原文；该节点不得视为已证实。"
        elif evidence_by_id:
            status = "VERIFIED_SOURCE"
            boundary = "原文只支持本节点陈述，不自动证明后续经营、财务或方向判断。"
            supported_steps.add(step)
        elif node.get("statement_class") == "RESEARCH_INFERENCE":
            premises = node.get("premise_node_ids") or []
            status = "SUPPORTED_INFERENCE" if premises else "INFERENCE_ONLY"
            boundary = (
                "由已列前提推导，仍需经营变量或公司披露验证。"
                if premises
                else "当前为研究假设，尚无直接原文证据。"
            )
            supported_steps.add(step)
        elif node.get("statement_class") == "CALCULATED_FACT":
            status = "SUPPORTED_INFERENCE"
            boundary = "行情计算用于检验反应强弱，不构成单一事件因果证明。"
            supported_steps.add(step)
        else:
            status = "INFERENCE_ONLY"
            boundary = "当前节点缺少直接来源，仅保留为待验证研究推断。"

        node_statuses.append(
            {
                "step": step,
                "node_id": node.get("node_id"),
                "node_type": node.get("node_type"),
                "statement_zh": node.get("statement_zh") or node.get("statement"),
                "statement_class": node.get("statement_class"),
                "status": status,
                "status_zh": STATUS_ZH[status],
                "boundary_zh": boundary,
                "condition_zh": node.get("condition_zh"),
                "invalidation_zh": node.get("invalidation_zh"),
                "evidence_ids": evidence_ids,
                "missing_evidence_ids": missing_ids,
            }
        )

    verified = sum(row["status"] == "VERIFIED_SOURCE" for row in node_statuses)
    missing = sum(row["status"] == "EVIDENCE_MISSING" for row in node_statuses)
    inference = len(node_statuses) - verified - missing
    coverage = (verified + 0.5 * sum(row["status"] == "SUPPORTED_INFERENCE" for row in node_statuses)) / max(len(nodes), 1)
    return {
        "node_statuses": node_statuses,
        "evidence_registry": list(registry.values()),
        "verified_count": verified,
        "inference_count": inference,
        "missing_count": missing,
        "coverage_ratio": round(coverage, 4),
    }


def _observations(impact: Mapping[str, Any]) -> list[dict[str, Any]]:
    continuous = (impact.get("market_window") or {}).get("continuous_window") or []
    if isinstance(continuous, Mapping):
        continuous = continuous.get("observations") or []
    return [dict(row) for row in continuous]


def _t0_index(impact: Mapping[str, Any], observations: Sequence[Mapping[str, Any]]) -> int:
    fixed = (impact.get("market_window") or {}).get("fixed_windows") or {}
    t0_date = (fixed.get("T0") or {}).get("actual_date")
    for index, row in enumerate(observations):
        if t0_date and row.get("actual_date") == t0_date:
            return index
    return min(20, max(len(observations) - 1, 0))


def _daily_series(impact: Mapping[str, Any]) -> list[dict[str, float | int]]:
    observations = _observations(impact)
    if len(observations) < 2:
        return []
    t0 = _t0_index(impact, observations)
    rows: list[dict[str, float | int]] = []
    for index in range(1, len(observations)):
        previous, current = observations[index - 1], observations[index]
        industry_previous = float(previous["industry_value"])
        market_previous = float(previous["market_value"])
        industry_return = float(current["industry_value"]) / industry_previous - 1
        market_return = float(current["market_value"]) / market_previous - 1
        rows.append(
            {
                "relative_day": index - t0,
                "industry_return": industry_return,
                "market_return": market_return,
                "simple_abnormal": industry_return - market_return,
            }
        )
    return rows


def _ols(rows: Sequence[Mapping[str, float | int]]) -> tuple[float, float, float]:
    xs = [float(row["market_return"]) for row in rows]
    ys = [float(row["industry_return"]) for row in rows]
    if len(xs) < 2:
        return 0.0, 1.0, 0.0
    mean_x, mean_y = statistics.fmean(xs), statistics.fmean(ys)
    variance_x = sum((value - mean_x) ** 2 for value in xs)
    beta = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / variance_x if variance_x else 1.0
    alpha = mean_y - beta * mean_x
    residuals = [y - (alpha + beta * x) for x, y in zip(xs, ys)]
    residual_std = statistics.stdev(residuals) if len(residuals) > 1 else 0.0
    return alpha, beta, residual_std


def _window_stats(rows: Sequence[Mapping[str, float | int]], start: int, end: int) -> dict[str, Any]:
    selected = [row for row in rows if start <= int(row["relative_day"]) <= end]
    simple = [float(row["simple_abnormal"]) for row in selected]
    model = [float(row["market_model_abnormal"]) for row in selected]
    simple_car = sum(simple)
    model_car = sum(model)
    volatility = statistics.stdev(model) if len(model) > 1 else 0.0
    mean = statistics.fmean(model) if model else 0.0
    t_value = mean / (volatility / math.sqrt(len(model))) if volatility and model else 0.0
    return {
        "range": f"T{start:+d}至T{end:+d}" if end <= 0 else f"D{start}至D{end}",
        "sample_count": len(selected),
        "simple_car": _round(simple_car),
        "market_model_car": _round(model_car),
        "average_abnormal_return": _round(mean),
        "volatility": _round(volatility),
        "t_value": _round(t_value, 3),
        "direction": _direction(model_car),
    }


def build_event_study(impact: Mapping[str, Any]) -> dict[str, Any]:
    daily = _daily_series(impact)
    estimation = [row for row in daily if -20 <= int(row["relative_day"]) <= -2]
    alpha, beta, residual_std = _ols(estimation)
    for row in daily:
        row["market_model_abnormal"] = float(row["industry_return"]) - (
            alpha + beta * float(row["market_return"])
        )
    windows = {
        key: _window_stats(daily, start, end)
        for key, (start, end) in WINDOW_RANGES.items()
    }
    placebo: list[dict[str, Any]] = []
    for end in range(-18, -1):
        start = end - 1
        stats = _window_stats(daily, start, end)
        if stats["sample_count"] == 2:
            placebo.append({"start": start, "end": end, "market_model_car": stats["market_model_car"]})
    event_abs = abs(float(windows["EVENT"]["market_model_car"]))
    percentile = (
        sum(abs(float(row["market_model_car"])) <= event_abs for row in placebo) / len(placebo)
        if placebo
        else 0.0
    )
    pretrend = windows["PRETREND"]
    pretrend_contaminated = abs(float(pretrend["t_value"])) >= 2 or abs(float(pretrend["market_model_car"])) >= 0.05
    simple_direction = _direction(float(windows["EVENT"]["simple_car"]))
    model_direction = windows["EVENT"]["direction"]
    cutoff_blocked = impact.get("event_id") == "event-07"
    interpretation = (
        "截止日门禁生效：可展示价格计算，但不得用截止日后锚点行情提升归因结论。"
        if cutoff_blocked
        else "统计结果仅用于验证行业相对反应；混杂因素和前趋势意味着不能据此确认单一事件因果。"
    )
    return {
        "method": "MARKET_ADJUSTED_AND_MARKET_MODEL",
        "estimation_window": "T-20至T-2",
        "market_model": {
            "alpha": _round(alpha),
            "beta": _round(beta),
            "residual_std": _round(residual_std),
            "estimation_count": len(estimation),
        },
        "windows": windows,
        "robustness": {
            "placebo_windows": placebo,
            "event_abs_car_percentile": round(percentile, 4),
            "model_direction_consistent": simple_direction == model_direction,
            "pretrend_contaminated": pretrend_contaminated,
        },
        "cutoff_blocked": cutoff_blocked,
        "attribution_decision": "ABSTAIN_CUTOFF" if cutoff_blocked else "STATISTICAL_VALIDATION_ONLY",
        "interpretation_zh": interpretation,
    }


def _company_matrix_row(company: Mapping[str, Any]) -> dict[str, Any]:
    mechanism = company.get("mechanism_chain") or {}
    binding = company.get("binding_review") or {}
    confounder = company.get("confounder_argument") or {}
    counter = company.get("counterevidence_review") or {}
    findings = counter.get("findings") or []
    return {
        "company_id": company.get("company_id"),
        "company_code": company.get("company_code"),
        "company_name": company.get("company_name"),
        "horizon_directions": mechanism.get("horizon_directions") or {},
        "selection_reason_zh": binding.get("selection_basis") or mechanism.get("conditions", [None])[0],
        "trading_status": (company.get("trading_status_review") or {}).get("overall_status"),
        "confounder_summary_zh": confounder.get("argument_zh"),
        "counterevidence_count": len(findings),
    }


def build_industry_company_matrix(event: Mapping[str, Any]) -> list[dict[str, Any]]:
    companies = {str(row.get("company_id")): row for row in event.get("companies") or []}
    matrix: list[dict[str, Any]] = []
    for impact in event.get("industry_impacts") or []:
        closure = impact["research_closure"]
        event_window = closure["event_study"]["windows"]["EVENT"]
        linked = []
        for link in impact.get("company_links") or []:
            company = companies.get(str(link.get("company_id")))
            if company:
                linked.append(_company_matrix_row(company))
        matrix.append(
            {
                "event_industry_mapping_id": impact.get("event_industry_mapping_id"),
                "industry_name_zh": impact.get("display_name_zh") or impact.get("sw1_name_at_event"),
                "impact_tier": impact.get("impact_tier"),
                "industry_horizon_directions": impact.get("horizon_directions") or {},
                "evidence_coverage_ratio": closure["coverage_ratio"],
                "event_car": event_window["market_model_car"],
                "event_car_direction": event_window["direction"],
                "robustness_percentile": closure["event_study"]["robustness"]["event_abs_car_percentile"],
                "cutoff_blocked": closure["event_study"]["cutoff_blocked"],
                "companies": linked,
            }
        )
    return matrix


def enrich_bundle(bundle: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    for event in bundle.get("events") or []:
        for impact in event.get("industry_impacts") or []:
            closure = build_research_closure(impact)
            closure["event_study"] = build_event_study(impact)
            impact["research_closure"] = closure
        event["industry_company_matrix"] = build_industry_company_matrix(event)
    bundle.setdefault("summary", {})["industry_research_closure_version"] = "v3"
    return bundle


__all__ = [
    "build_event_study",
    "build_industry_company_matrix",
    "build_research_closure",
    "enrich_bundle",
]
