from pathlib import Path

from fingoose_training.research_content import build_event_research_content
from fingoose_training.ui_reference import load_ui_reference


def test_event_01_research_content_has_complete_three_horizons():
    project = Path(__file__).resolve().parents[2]
    bundle = load_ui_reference(project / "work/company_impact_high_quality_v2_candidate/ui/ui_data_bundle.js")
    event = next(row for row in bundle["events"] if row["event_id"] == "event-01")
    content = build_event_research_content(event)
    assert content["schema_version"] == "research-content-v1"
    assert content["event_id"] == "event-01"
    assert set(content["horizon_analysis"]) == {"IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM"}
    for horizon in content["horizon_analysis"].values():
        assert horizon["summary_zh"].strip()
        assert horizon["mechanism_node_ids"]
        assert horizon["evidence_ids"]
    assert content["main_path_node_ids"][-1].endswith("market-validation")
    assert len({content["horizon_analysis"][key]["summary_zh"] for key in ("IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM")}) == 3
