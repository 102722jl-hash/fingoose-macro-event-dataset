from pathlib import Path

import pytest

from fingoose_training.ui_reference import UIReferenceError, load_ui_reference


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
UI_PATH = PROJECT / "work/company_impact_high_quality_v2_candidate/ui/ui_data_bundle.js"


def test_load_ui_reference_reads_exact_json_wrapper():
    bundle = load_ui_reference(UI_PATH)
    assert bundle["dataset_version"] == "fingoose-company-impact-high-quality-v2-candidate"
    assert [row["event_id"] for row in bundle["events"]] == [f"event-{i:02d}" for i in range(1, 11)]


def test_load_ui_reference_rejects_arbitrary_javascript(scratch_path):
    path = scratch_path / "bundle.js"
    path.write_text("alert(1)", encoding="utf-8")
    with pytest.raises(UIReferenceError, match="exact JSON wrapper"):
        load_ui_reference(path)
