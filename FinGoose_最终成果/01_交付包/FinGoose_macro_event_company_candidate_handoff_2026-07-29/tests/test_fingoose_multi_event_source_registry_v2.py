from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "configs/industry_impact_v2/multi_event_source_registry.jsonl"
TARGET_EVENT_IDS = {f"event-{number:02d}" for number in range(6, 11)}
EARLY_EVENT_IDS = {f"event-{number:02d}" for number in range(2, 6)}

EXPECTED_MAPPING_IDS = {
    "event06-opec-jmmc": [
        "event-industry-event-06-801960",
        "event-industry-event-06-801950",
        "event-industry-event-06-801030",
        "event-industry-event-06-801170",
        "event-industry-event-06-801160",
        "event-industry-event-06-801730",
        "event-industry-event-06-801010",
    ],
    "event06-eia-opec-price": [
        "event-industry-event-06-801960",
        "event-industry-event-06-801030",
        "event-industry-event-06-801170",
        "event-industry-event-06-801160",
    ],
    "event06-eia-oil-use-price": [
        "event-industry-event-06-801030",
        "event-industry-event-06-801170",
        "event-industry-event-06-801160",
    ],
    "event06-iata-fuel": ["event-industry-event-06-801170"],
    "event07-imo-galaxy-leader": [
        "event-industry-event-07-801170",
        "event-industry-event-07-801960",
        "event-industry-event-07-801080",
        "event-industry-event-07-801880",
        "event-industry-event-07-801110",
        "event-industry-event-07-801890",
        "event-industry-event-07-801030",
    ],
    "event07-eia-time-freight": [
        "event-industry-event-07-801170",
        "event-industry-event-07-801960",
        "event-industry-event-07-801080",
        "event-industry-event-07-801880",
        "event-industry-event-07-801110",
        "event-industry-event-07-801890",
        "event-industry-event-07-801030",
    ],
    "event07-eia-bunker": [
        "event-industry-event-07-801170",
        "event-industry-event-07-801960",
        "event-industry-event-07-801080",
        "event-industry-event-07-801880",
        "event-industry-event-07-801110",
        "event-industry-event-07-801890",
        "event-industry-event-07-801030",
    ],
    "event07-unnews-unctad": [
        "event-industry-event-07-801170",
        "event-industry-event-07-801960",
        "event-industry-event-07-801080",
        "event-industry-event-07-801880",
        "event-industry-event-07-801110",
        "event-industry-event-07-801890",
        "event-industry-event-07-801030",
    ],
    "event08-boj": [
        "event-industry-event-08-801780",
        "event-industry-event-08-801790",
        "event-industry-event-08-801170",
        "event-industry-event-08-801880",
        "event-industry-event-08-801890",
        "event-industry-event-08-801080",
        "event-industry-event-08-801050",
    ],
    "event08-boj-fsr-oct23": [
        "event-industry-event-08-801780",
        "event-industry-event-08-801790",
    ],
    "event08-boj-fsr-apr23": [
        "event-industry-event-08-801780",
        "event-industry-event-08-801790",
    ],
    "event08-bis-carry": [
        "event-industry-event-08-801780",
        "event-industry-event-08-801790",
    ],
    "event09-pbc": [
        "event-industry-event-09-801790",
        "event-industry-event-09-801180",
        "event-industry-event-09-801780",
        "event-industry-event-09-801710",
        "event-industry-event-09-801140",
        "event-industry-event-09-801110",
        "event-industry-event-09-801720",
        "event-industry-event-09-801200",
    ],
    "event09-pbc-q2": [
        "event-industry-event-09-801180",
        "event-industry-event-09-801780",
        "event-industry-event-09-801710",
        "event-industry-event-09-801140",
        "event-industry-event-09-801110",
        "event-industry-event-09-801720",
    ],
    "event09-xinhua-rrr": [
        "event-industry-event-09-801790",
        "event-industry-event-09-801780",
    ],
    "event10-whitehouse-order": [
        "event-industry-event-10-801080",
        "event-industry-event-10-801110",
        "event-industry-event-10-801730",
        "event-industry-event-10-801130",
        "event-industry-event-10-801890",
        "event-industry-event-10-801880",
        "event-industry-event-10-801170",
        "event-industry-event-10-801030",
        "event-industry-event-10-801010",
    ],
    "event10-whitehouse-fact": [
        "event-industry-event-10-801080",
        "event-industry-event-10-801110",
        "event-industry-event-10-801730",
        "event-industry-event-10-801130",
        "event-industry-event-10-801890",
        "event-industry-event-10-801880",
        "event-industry-event-10-801170",
        "event-industry-event-10-801030",
        "event-industry-event-10-801010",
    ],
    "event10-usitc-pub5405": [
        "event-industry-event-10-801080",
        "event-industry-event-10-801110",
        "event-industry-event-10-801730",
        "event-industry-event-10-801130",
        "event-industry-event-10-801890",
        "event-industry-event-10-801880",
        "event-industry-event-10-801170",
        "event-industry-event-10-801030",
        "event-industry-event-10-801010",
    ],
    "event10-ustr-origin": [
        "event-industry-event-10-801730",
        "event-industry-event-10-801880",
    ],
}


def _target_rows() -> list[dict]:
    rows = [json.loads(line) for line in REGISTRY.read_text(encoding="utf-8").splitlines()]
    return [row for row in rows if row["event_id"] in TARGET_EVENT_IDS]


def test_event_06_through_10_source_ids_and_mapping_order_are_stable() -> None:
    rows = _target_rows()

    assert {row["source_id"] for row in rows} == set(EXPECTED_MAPPING_IDS)
    assert {
        row["source_id"]: row["supports_mapping_ids"] for row in rows
    } == EXPECTED_MAPPING_IDS


def test_event_06_through_10_audit_text_is_present_and_not_question_mark_corrupted() -> None:
    for row in _target_rows():
        for field in ("publisher", "title", "required_quote", "evidence_locator"):
            value = row[field]
            assert isinstance(value, str), f"{row['source_id']}.{field} must be a string"
            assert value.strip(), f"{row['source_id']}.{field} must not be blank"
            assert "?" not in value, f"{row['source_id']}.{field} contains ASCII question marks"



def test_event_02_through_05_audit_text_is_present_and_not_question_mark_corrupted() -> None:
    rows = [
        json.loads(line)
        for line in REGISTRY.read_text(encoding="utf-8").splitlines()
    ]
    early_rows = [row for row in rows if row["event_id"] in EARLY_EVENT_IDS]

    assert len(early_rows) == 16
    for row in early_rows:
        for field in ("publisher", "title", "required_quote", "evidence_locator"):
            value = row[field]
            assert isinstance(value, str), f"{row['source_id']}.{field} must be a string"
            assert value.strip(), f"{row['source_id']}.{field} must not be blank"
            assert "?" not in value, f"{row['source_id']}.{field} contains ASCII question marks"