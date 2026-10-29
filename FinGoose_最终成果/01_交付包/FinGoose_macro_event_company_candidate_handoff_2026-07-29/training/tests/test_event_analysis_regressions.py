from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from fingoose_training.validation import validate_datasets


DATA_ROOT = Path(__file__).resolve().parents[1] / "data"


def _sample(sample_id: str) -> dict:
    return next(
        json.loads(line)
        for line in (DATA_ROOT / "sft_dataset.jsonl").read_text(encoding="utf-8").splitlines()
        if json.loads(line).get("sample_id") == sample_id
    )


def test_event_analysis_merges_complete_who_evidence_records() -> None:
    sample = _sample("event-01-event-analysis")
    records = {
        row["evidence_id"]: row
        for row in sample["metadata"]["evidence_registry"]
        if row.get("evidence_id") in {"event01-who-pandemic", "event01-who-sitrep51"}
    }

    assert records["event01-who-pandemic"]["missing"] is False
    assert records["event01-who-pandemic"]["original_quote"]
    assert records["event01-who-pandemic"]["locator"]
    assert records["event01-who-sitrep51"]["missing"] is False
    assert records["event01-who-sitrep51"]["original_quote"]
    assert records["event01-who-sitrep51"]["locator"]


def test_event_analysis_closure_is_based_on_selected_main_path() -> None:
    sample = _sample("event-01-event-analysis")
    metadata = sample["metadata"]
    graph = metadata["reasoning_chain"]

    assert metadata["conclusion_lineage"]["closure_status"] == "CLOSED"
    assert graph["closure_gate"]["status"] == "CLOSED"
    assert graph["main_path_node_ids"][-1] == "event-01-market-validation"
    assert graph["main_path_node_ids"][:2] == [
        "milestone-event-01-1f0d9ae571b0",
        "event-01-shock",
    ]


def test_event_analysis_exposes_all_event_industries_and_companies() -> None:
    sample = _sample("event-01-event-analysis")
    metadata = sample["metadata"]

    assert len(metadata["related_industry_ids"]) == 8
    assert len(metadata["related_company_codes"]) == 3
    answer = sample["messages"][2]["content"]
    for company_name in ("中国国航", "上海机场", "达安基因"):
        assert company_name in answer


def test_real_dataset_contains_no_common_utf8_mojibake() -> None:
    paths = [DATA_ROOT / "unified_events.jsonl", DATA_ROOT / "sft_dataset.jsonl"]
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    for token in ("浣犳槸", "浜嬩欢", "寰呰ˉ鍏呴檲杩", "â"):  # typical UTF-8-as-GBK remnants
        assert token not in text


def test_validation_rejects_mojibake_in_training_messages() -> None:
    samples = [
        json.loads(line)
        for line in (DATA_ROOT / "sft_dataset.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    events = [
        json.loads(line)
        for line in (DATA_ROOT / "unified_events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    broken = deepcopy(samples)
    broken[0]["messages"][0]["content"] = "浣犳槸宏观事件研究助手"

    report = validate_datasets(
        events, broken, expected_events={event["event_id"] for event in events}
    )

    assert any(
        error["code"] == "TEXT_ENCODING_GARBLED" for error in report["errors"]
    )
