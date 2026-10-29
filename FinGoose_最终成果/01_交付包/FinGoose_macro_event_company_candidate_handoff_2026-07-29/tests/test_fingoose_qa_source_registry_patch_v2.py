from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_source_registry_patch_closes_event_04_and_event_07_transport_gaps() -> None:
    path = ROOT / "configs/qa_reasoning_v2/official_source_registry_patch_001.jsonl"
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert {row["event_id"] for row in rows} == {"event-04", "event-07"}
    assert all(row["usage_boundary"] == "PREDICTION_VISIBLE" for row in rows)
    assert all(row["required_quote"] and row["evidence_locator"] for row in rows)
