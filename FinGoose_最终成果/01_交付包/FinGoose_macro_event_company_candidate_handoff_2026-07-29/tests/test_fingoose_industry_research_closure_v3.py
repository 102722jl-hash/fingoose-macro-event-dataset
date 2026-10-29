from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


def _bundle() -> dict:
    from fingoose_company_impact_qa_ui_v2 import build_ui_bundle

    return build_ui_bundle(
        ROOT,
        qa_root=ROOT / "work/qa_reasoning_pilot_v2_candidate",
    )


def test_all_industries_have_seven_classified_nodes_and_bidirectional_evidence() -> None:
    bundle = _bundle()
    impacts = [impact for event in bundle["events"] for impact in event["industry_impacts"]]
    assert len(impacts) == 77
    valid = {
        "VERIFIED_SOURCE",
        "SUPPORTED_INFERENCE",
        "INFERENCE_ONLY",
        "EVIDENCE_MISSING",
    }
    for impact in impacts:
        closure = impact["research_closure"]
        nodes = closure["node_statuses"]
        assert len(nodes) == 7
        assert {node["status"] for node in nodes} <= valid
        registry = {row["evidence_id"]: row for row in closure["evidence_registry"]}
        for node in nodes:
            for evidence_id in node["evidence_ids"]:
                assert evidence_id in registry
                assert node["step"] in registry[evidence_id]["supports_steps"]
        assert closure["verified_count"] + closure["inference_count"] + closure["missing_count"] == 7
        assert 0 <= closure["coverage_ratio"] <= 1


def test_event_studies_cover_four_windows_and_robustness() -> None:
    bundle = _bundle()
    studies = [
        impact["research_closure"]["event_study"]
        for event in bundle["events"]
        for impact in event["industry_impacts"]
    ]
    assert len(studies) == 77
    for study in studies:
        assert set(study["windows"]) == {"PRETREND", "EVENT", "SHORT", "MEDIUM"}
        assert study["estimation_window"] == "T-20至T-2"
        assert study["market_model"]["estimation_count"] >= 10
        for window in study["windows"].values():
            assert window["sample_count"] > 0
            assert window["direction"] in {"POSITIVE", "NEGATIVE", "FLAT"}
            assert isinstance(window["simple_car"], float)
            assert isinstance(window["market_model_car"], float)
        robustness = study["robustness"]
        assert robustness["placebo_windows"]
        assert 0 <= robustness["event_abs_car_percentile"] <= 1
        assert isinstance(robustness["model_direction_consistent"], bool)
        assert "pretrend_contaminated" in robustness


def test_event_07_keeps_cutoff_attribution_gate() -> None:
    event = next(row for row in _bundle()["events"] if row["event_id"] == "event-07")
    for impact in event["industry_impacts"]:
        study = impact["research_closure"]["event_study"]
        assert study["cutoff_blocked"] is True
        assert study["attribution_decision"] == "ABSTAIN_CUTOFF"
        assert "截止" in study["interpretation_zh"]


def test_each_event_has_an_industry_company_matrix() -> None:
    bundle = _bundle()
    assert len(bundle["events"]) == 10
    for event in bundle["events"]:
        matrix = event["industry_company_matrix"]
        assert len(matrix) == len(event["industry_impacts"])
        for row in matrix:
            assert set(row["industry_horizon_directions"]) == {
                "IMMEDIATE",
                "SHORT_TERM",
                "MEDIUM_TERM",
            }
            assert "event_car" in row
            assert "evidence_coverage_ratio" in row
            assert isinstance(row["companies"], list)
