import json
from pathlib import Path

from fingoose_training.sft_projector import project_sft_samples


TRAINING_ROOT = Path(__file__).resolve().parents[1]
TRUNCATION_MARKER = "[内容已按训练长度上限截断]"


def test_all_real_samples_fit_without_hard_truncation():
    unified_path = TRAINING_ROOT / "data" / "unified_events.jsonl"
    events = [
        json.loads(line)
        for line in unified_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    samples = project_sft_samples(events)

    assert len(events) == 10
    assert len(samples) == 157
    assert {sample["task_type"] for sample in samples} == {
        "EVENT_ANALYSIS",
        "INDUSTRY_IMPACT",
        "COMPANY_IMPACT",
        "EVENT_QA",
    }
    assert all(
        TRUNCATION_MARKER not in message["content"]
        for sample in samples
        for message in sample["messages"]
    )
    assert all(
        isinstance(message["content"], str) and message["content"].strip()
        for sample in samples
        for message in sample["messages"]
    )
    assert all(
        sum(len(message["content"]) for message in sample["messages"]) <= 2000
        for sample in samples
    )

    events_by_id = {event["event_id"]: event for event in events}
    for sample in samples:
        event = events_by_id[sample["event_id"]]
        industry_ids = {
            industry["event_industry_mapping_id"]
            for industry in event.get("industries", [])
        }
        company_codes = {
            company["company_code"]
            for company in event.get("companies", [])
            if company.get("company_code")
        }
        metadata = sample["metadata"]
        assert set(metadata["related_industry_ids"]) <= industry_ids
        assert set(metadata["related_company_codes"]) <= company_codes
