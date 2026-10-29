"""Strict reader for the controlled UI reference bundle."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

UI_PREFIX = "window.FINGOOSE_COMPANY_IMPACT_V2="
UI_SUFFIX = ";"
EXPECTED_UI_DATASET_VERSION = "fingoose-company-impact-high-quality-v2-candidate"
EVIDENCE_ENRICHMENTS_PATH = Path(__file__).resolve().parents[1] / "data" / "evidence_enrichments.json"


class UIReferenceError(ValueError):
    """Raised when the UI reference is not the expected JSON wrapper."""


def load_ui_reference(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text.startswith(UI_PREFIX) or not text.endswith(UI_SUFFIX):
        raise UIReferenceError(f"{path}: expected exact JSON wrapper")
    raw = text[len(UI_PREFIX) : -len(UI_SUFFIX)]
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise UIReferenceError(f"{path}: invalid wrapped JSON: {exc.msg}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        raise UIReferenceError(f"{path}: expected object with events")
    ids = [row.get("event_id") for row in payload["events"] if isinstance(row, dict)]
    if len(ids) != 10 or len(set(ids)) != 10:
        raise UIReferenceError(f"{path}: expected 10 unique events")
    if payload.get("dataset_version") != EXPECTED_UI_DATASET_VERSION:
        raise UIReferenceError(
            f"{path}: unexpected dataset_version={payload.get('dataset_version')}"
        )
    try:
        enrichment = json.loads(EVIDENCE_ENRICHMENTS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UIReferenceError(
            f"{EVIDENCE_ENRICHMENTS_PATH}: invalid evidence enrichment"
        ) from exc
    if enrichment.get("schema_version") != "evidence-enrichment-v1":
        raise UIReferenceError("unexpected evidence enrichment schema")
    events_by_id = {
        str(event["event_id"]): event
        for event in payload["events"]
        if isinstance(event, dict) and event.get("event_id")
    }
    for record in enrichment.get("records") or []:
        event_id = str(record.get("event_id") or "")
        if event_id not in events_by_id or not record.get("evidence_id"):
            raise UIReferenceError("evidence enrichment references unknown event or evidence")
        events_by_id[event_id].setdefault("evidence_enrichments", []).append(record)

    return payload

def index_ui_events(bundle: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    events = bundle.get("events")
    if not isinstance(events, list):
        raise UIReferenceError("ui reference missing events")
    result: dict[str, dict[str, Any]] = {}
    for row in events:
        if not isinstance(row, dict) or not row.get("event_id"):
            raise UIReferenceError("ui reference contains event without event_id")
        event_id = str(row["event_id"])
        if event_id in result:
            raise UIReferenceError(f"duplicate event_id={event_id}")
        result[event_id] = row
    return result


__all__ = [
    "EXPECTED_UI_DATASET_VERSION",
    "UI_PREFIX",
    "UI_SUFFIX",
    "UIReferenceError",
    "index_ui_events",
    "load_ui_reference",
]
