"""Fail-closed causal-identification levels for market-event records."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence


DESCRIPTIVE_GATES = (
    "market_windows_complete",
    "market_benchmark_complete",
    "industry_benchmark_complete",
    "continuous_trading_verified",
)
QUASI_GATES = (
    *DESCRIPTIVE_GATES,
    "comparison_group_defined",
    "pretrend_passed",
    "confounders_controlled",
)
IDENTIFIED_GATES = (
    *QUASI_GATES,
    "robustness_passed",
    "counterevidence_passed",
)


def classify_causal_identification(
    gates: Mapping[str, Any],
    *,
    method: str | None = None,
    confounders: Sequence[Any] = (),
    counterevidence: Sequence[Any] = (),
) -> dict[str, Any]:
    """Classify identification without coercing unknown values to approval."""

    gate_results = {
        name: gates.get(name) is True
        for name in IDENTIFIED_GATES
    }
    if all(gate_results[name] for name in IDENTIFIED_GATES):
        status = "IDENTIFIED"
    elif all(gate_results[name] for name in QUASI_GATES):
        status = "QUASI_EXPERIMENTAL_CANDIDATE"
    elif all(gate_results[name] for name in DESCRIPTIVE_GATES):
        status = "DESCRIPTIVE_EVENT_STUDY"
    else:
        status = "NOT_IDENTIFIED"

    allowed = status == "IDENTIFIED"
    return {
        "status": status,
        "causal_attribution_allowed": allowed,
        "causal_conclusion": "IDENTIFIED_EFFECT" if allowed else "ABSTAIN",
        "method": method,
        "gate_results": gate_results,
        "unmet_conditions": [
            name for name in IDENTIFIED_GATES if not gate_results[name]
        ],
        "confounders": deepcopy(list(confounders)),
        "counterevidence": deepcopy(list(counterevidence)),
        "boundary_zh": (
            "预设因果识别门禁全部通过，可在所声明方法和范围内报告识别结果。"
            if allowed
            else "行情仅描述窗口表现和机制一致性；因果识别条件未全部满足，因此拒绝归因。"
        ),
    }


__all__ = [
    "DESCRIPTIVE_GATES",
    "QUASI_GATES",
    "IDENTIFIED_GATES",
    "classify_causal_identification",
]
