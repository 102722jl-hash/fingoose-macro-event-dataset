"""Transparent compliance metrics for generated FinGoose answers."""

from __future__ import annotations

from collections import Counter
from typing import Any


UNCERTAINTY_TERMS = ("不确定", "证据不足", "无法确认", "尚待", "未知")
HORIZON_TERMS = ("即时", "短期", "中期")


def _rate(flags: list[bool]) -> float:
    return round(sum(flags) / len(flags), 6) if flags else 0.0


def _group_counts(values: list[str]) -> dict[str, dict[str, int]]:
    return {
        value: {"sample_count": count}
        for value, count in sorted(Counter(values).items())
    }


def evaluate_predictions(
    samples: list[dict[str, Any]], predictions: list[dict[str, Any]]
) -> dict[str, Any]:
    if len(samples) != len(predictions):
        raise ValueError("samples and predictions must have the same length")

    evidence_flags: list[bool] = []
    horizon_flags: list[bool] = []
    uncertainty_flags: list[bool] = []
    nonempty_flags: list[bool] = []
    for sample, prediction in zip(samples, predictions):
        text = str(prediction.get("text", "")).strip()
        evidence_ids = sample.get("metadata", {}).get("evidence_ids", [])
        evidence_flags.append(
            True if not evidence_ids else any(str(item) in text for item in evidence_ids)
        )
        horizon_flags.append(all(term in text for term in HORIZON_TERMS))
        uncertainty_flags.append(any(term in text for term in UNCERTAINTY_TERMS))
        nonempty_flags.append(bool(text))

    return {
        "metric_scope": "rule_based_compliance_not_semantic_correctness",
        "sample_count": len(samples),
        "nonempty_prediction_rate": _rate(nonempty_flags),
        "evidence_reference_valid_rate": _rate(evidence_flags),
        "horizon_term_coverage_rate": _rate(horizon_flags),
        "uncertainty_language_rate": _rate(uncertainty_flags),
        "by_task": _group_counts([row.get("task_type", "UNKNOWN") for row in samples]),
        "by_event": _group_counts([row.get("event_id", "UNKNOWN") for row in samples]),
    }
