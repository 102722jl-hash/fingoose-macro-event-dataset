"""Preserve the total-industry count in time-specific horizon narratives."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import fingoose_qa_reasoning_v2_impl_003 as _base


ANSWER_LAYER_KEYS = _base.ANSWER_LAYER_KEYS
DIRECTION_ZH = _base.DIRECTION_ZH
HORIZON_KEYS = _base.HORIZON_KEYS
QaBundle = _base.QaBundle
TASK_LABELS = _base.TASK_LABELS
TASK_TYPES = _base.TASK_TYPES
VERDICT_ZH = _base.VERDICT_ZH
WINDOW_KEYS = _base.WINDOW_KEYS
load_existing_source_fetches = _base.load_existing_source_fetches
read_jsonl = _base.read_jsonl
validate_qa_bundle = _base.validate_qa_bundle
write_candidate_package = _base.write_candidate_package
write_jsonl = _base.write_jsonl


def build_qa_records(root: Path) -> QaBundle:
    bundle = _base.build_qa_records(root)
    answers: list[dict[str, Any]] = []
    for source in bundle.answers:
        answer = dict(source)
        total = len(answer.get("industry_impacts") or [])
        reasoning = {
            horizon: dict(row)
            for horizon, row in (answer.get("horizon_reasoning_zh") or {}).items()
        }
        for horizon in HORIZON_KEYS:
            row = reasoning[horizon]
            text = str(row.get("reasoning_zh") or "")
            if "个行业" not in text:
                text = f"本事件共覆盖 {total} 个行业。{text}"
            row["reasoning_zh"] = text
        answer["horizon_reasoning_zh"] = reasoning
        answer["horizon_summary_zh"] = {
            horizon: reasoning[horizon]["reasoning_zh"] for horizon in HORIZON_KEYS
        }
        if answer.get("task_type") == "MAIN_REASONING":
            answer["answer_focus_zh"] = " ".join(
                reasoning[horizon]["reasoning_zh"] for horizon in HORIZON_KEYS
            )
        answers.append(answer)
    return QaBundle(cases=bundle.cases, answers=answers, labels=bundle.labels)


__all__ = [
    "ANSWER_LAYER_KEYS",
    "DIRECTION_ZH",
    "HORIZON_KEYS",
    "QaBundle",
    "TASK_LABELS",
    "TASK_TYPES",
    "VERDICT_ZH",
    "WINDOW_KEYS",
    "build_qa_records",
    "load_existing_source_fetches",
    "read_jsonl",
    "validate_qa_bundle",
    "write_candidate_package",
    "write_jsonl",
]
