from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_official_registry_covers_ten_events_with_direct_sources() -> None:
    path = ROOT / "configs/qa_reasoning_v2/official_source_registry.jsonl"
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert {row["event_id"] for row in rows} == {
        f"event-{number:02d}" for number in range(1, 11)
    }
    assert len({row["source_id"] for row in rows}) == len(rows)
    for row in rows:
        assert row["source_url"].startswith("http")
        assert "google." not in row["source_url"]
        assert "bing." not in row["source_url"]
        assert row["required_quote"]
        assert row["evidence_locator"]
        assert row["licence_status"] == "PUBLIC_REPRODUCIBLE_LICENSE_REVIEW_PENDING"
