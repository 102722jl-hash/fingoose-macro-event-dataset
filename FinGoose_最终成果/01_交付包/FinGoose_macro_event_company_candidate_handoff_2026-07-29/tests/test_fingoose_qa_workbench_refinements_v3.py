from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


def _answers() -> dict[tuple[str, str], dict]:
    from fingoose_qa_reasoning_v2 import build_qa_records

    return {
        (row["event_id"], row["task_type"]): row
        for row in build_qa_records(ROOT).answers
    }


def test_industry_inference_and_horizon_rows_keep_evidence_lineage() -> None:
    answers = _answers()
    for event_index in range(1, 11):
        answer = answers[(f"event-{event_index:02d}", "MAIN_REASONING")]
        for impact in answer["industry_impacts"]:
            assert impact["research_evidence_ids"]
        for horizon in answer["horizon_reasoning_zh"].values():
            assert horizon["evidence_ids"]


def test_market_verdicts_expose_strength_without_breaking_verdict_enum() -> None:
    answers = _answers()
    for event_index in range(1, 11):
        task = answers[(f"event-{event_index:02d}", "MARKET_VALIDATION")]["task_answer"]
        for result in task["industry_results"]:
            for verdict in result["horizon_verdicts"].values():
                assert verdict["strength"] in {"STRONG", "MODERATE", "WEAK", "NOT_ASSESSABLE"}
                assert verdict["strength_zh"]


def test_company_results_explain_selection_reason() -> None:
    answers = _answers()
    for event_index in range(1, 11):
        task = answers[(f"event-{event_index:02d}", "INDUSTRY_COMPANY")]["task_answer"]
        for company in task["company_results"]:
            assert company["selection_reason_zh"]


def test_refinement_controls_are_present_in_the_workbench() -> None:
    from fingoose_company_impact_qa_ui_v2 import build_ui_bundle, render_workbench

    html = render_workbench(
        build_ui_bundle(ROOT, qa_root=ROOT / "work/qa_reasoning_pilot_v2_candidate")
    )
    for marker in (
        "qaEvidenceFilter",
        "qaRefusalFilter",
        "data-horizon-view",
        "统计偏弱",
        "入选理由",
    ):
        assert marker in html
