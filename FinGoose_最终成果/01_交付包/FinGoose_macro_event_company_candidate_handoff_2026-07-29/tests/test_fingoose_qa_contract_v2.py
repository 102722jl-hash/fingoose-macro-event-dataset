from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


def test_event_profiles_cover_ten_events_and_four_tasks() -> None:
    from fingoose_qa_contract_v2 import TASK_TYPES, load_event_profiles

    profiles = load_event_profiles(
        ROOT / "configs/qa_reasoning_v2/qa_event_profiles.json"
    )
    assert [row["event_id"] for row in profiles] == [
        f"event-{number:02d}" for number in range(1, 11)
    ]
    assert all(set(row["questions"]) == set(TASK_TYPES) for row in profiles)
    assert all(row["prediction_cutoff_at"] for row in profiles)
    event_03 = next(row for row in profiles if row["event_id"] == "event-03")
    assert event_03["prediction_cutoff_at"] == "2022-03-19T18:00:00Z"
