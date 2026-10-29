"""Frozen ten-event contract for the event-linked QA candidate layer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


TASK_TYPES = (
    "MAIN_REASONING",
    "EVIDENCE_AUDIT",
    "MARKET_VALIDATION",
    "INDUSTRY_COMPANY",
)


def load_event_profiles(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    profiles = payload["events"]
    expected = [f"event-{number:02d}" for number in range(1, 11)]
    if [row["event_id"] for row in profiles] != expected:
        raise ValueError("QA_EVENT_SCOPE_MISMATCH")
    if any(set(row["questions"]) != set(TASK_TYPES) for row in profiles):
        raise ValueError("QA_TASK_CONTRACT_MISMATCH")
    return profiles
