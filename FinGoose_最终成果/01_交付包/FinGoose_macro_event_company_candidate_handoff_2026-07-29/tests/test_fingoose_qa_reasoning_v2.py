from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


EXPECTED_INDUSTRY_COUNTS = {
    "event-01": 8,
    "event-02": 8,
    "event-03": 8,
    "event-04": 8,
    "event-05": 7,
    "event-06": 7,
    "event-07": 7,
    "event-08": 7,
    "event-09": 8,
    "event-10": 9,
}


def test_build_qa_records_has_complete_public_contract() -> None:
    from fingoose_qa_reasoning_v2 import TASK_TYPES, build_qa_records

    bundle = build_qa_records(ROOT)
    assert len(bundle.cases) == 40
    assert len(bundle.answers) == 40
    assert len(bundle.labels) == 40
    assert len({row["case_id"] for row in bundle.cases}) == 40
    for event_id in EXPECTED_INDUSTRY_COUNTS:
        tasks = {
            row["task_type"] for row in bundle.cases if row["event_id"] == event_id
        }
        assert tasks == set(TASK_TYPES)
    for answer in bundle.answers:
        assert list(answer["answer_layers"]) == [
            "SOURCE_FACTS",
            "RESEARCH_INFERENCE",
            "CALCULATED_FACTS",
            "REFUSAL_AND_BOUNDARIES",
        ]
        assert answer["status"] == "PROPOSED"
        assert answer["review_status"] == "NEEDS_HUMAN_REVIEW"
        assert answer["formal_ready"] is False
        assert answer["sha_gate"] == "DEFERRED"
        assert len(answer["mechanism_chain"]) == 7
        assert set(answer["horizon_summary"]) == {
            "IMMEDIATE",
            "SHORT_TERM",
            "MEDIUM_TERM",
        }


def test_answers_retain_frozen_industry_counts_and_six_windows() -> None:
    from fingoose_qa_reasoning_v2 import build_qa_records

    bundle = build_qa_records(ROOT)
    main_answers = {
        row["event_id"]: row
        for row in bundle.answers
        if row["task_type"] == "MAIN_REASONING"
    }
    assert {
        event_id: len(answer["industry_impacts"])
        for event_id, answer in main_answers.items()
    } == EXPECTED_INDUSTRY_COUNTS
    for answer in main_answers.values():
        for window in answer["market_windows"]:
            assert list(window["fixed_windows"]) == [
                "T_MINUS_1",
                "T0",
                "D1",
                "D3",
                "D5",
                "D20",
            ]


def test_hidden_fields_never_enter_public_records() -> None:
    from fingoose_qa_reasoning_v2 import build_qa_records

    bundle = build_qa_records(ROOT)
    public_text = json.dumps([bundle.cases, bundle.answers], ensure_ascii=False)
    hidden_fields = (
        "expected_industry_mapping_ids",
        "expected_evidence_ids",
        "expected_market_window_ids",
        "hard_failure_labels",
    )
    assert all(field not in public_text for field in hidden_fields)
    assert all(label["expected_industry_mapping_ids"] for label in bundle.labels)


def test_validator_recalculates_formulas_and_required_abstentions() -> None:
    from fingoose_qa_reasoning_v2 import build_qa_records, validate_qa_bundle

    bundle = build_qa_records(ROOT)
    report = validate_qa_bundle(bundle)
    assert report["hard_failures"] == []
    assert report["market_formula_max_abs_error"] <= 1e-10
    assert report["required_abstention_count"] > 0
    assert report["event_count"] == 10


def test_event_07_does_not_leak_red_sea_anchor_past_cutoff() -> None:
    from fingoose_qa_reasoning_v2 import build_qa_records

    bundle = build_qa_records(ROOT)
    answer = next(
        row
        for row in bundle.answers
        if row["event_id"] == "event-07" and row["task_type"] == "MAIN_REASONING"
    )
    assert all(
        evidence["first_public_at"] <= "2023-10-10T23:59:59.999999Z"
        for evidence in answer["evidence"]
        if "T" in str(evidence.get("first_public_at") or "")
    )
    assert any(
        row["refusal_reason"] == "ANCHOR_POST_CUTOFF"
        for row in answer["refusals"]
    )


def test_build_writes_isolated_candidate_package(tmp_path: Path) -> None:
    from build_fingoose_qa_reasoning_v2 import build

    report = build(ROOT, tmp_path)
    assert report["event_count"] == 10
    assert report["case_count"] == 40
    assert report["answer_count"] == 40
    assert report["label_count"] == 40
    assert report["hard_failures"] == []
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["formal_ready"] is False
    assert manifest["sha_gate"] == "DEFERRED"
    assert (tmp_path / "evaluator_only" / "qa_labels.jsonl").exists()
