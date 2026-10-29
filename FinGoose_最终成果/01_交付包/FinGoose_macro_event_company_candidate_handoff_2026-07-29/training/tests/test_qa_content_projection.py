import json
from copy import deepcopy
from pathlib import Path

from fingoose_training.research_content import build_event_research_content
from fingoose_training.sft_projector import project_sft_samples
from fingoose_training.artifacts import resolve_project_root
from fingoose_training.loaders import load_source_bundle, load_ui_reference_bundle, read_json
from fingoose_training.unified_builder import build_unified_events
from fingoose_training.ui_reference import load_ui_reference
from fingoose_training.validation_impl_005 import _check


TRAINING_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = TRAINING_ROOT.parents[0]
UI_PATH = PROJECT_ROOT / "work" / "company_impact_high_quality_v2_candidate" / "ui" / "ui_data_bundle.js"
CONFIG_PATH = TRAINING_ROOT / "configs" / "dataset.json"


def _ui_event_10():
    bundle = load_ui_reference(UI_PATH)
    return next(event for event in bundle["events"] if event["event_id"] == "event-10")


def _qa_content(event):
    content = build_event_research_content(event)
    return next(row for row in content["qa_sections"] if row["case_id"] == "qa-event-10-market-validation")


def test_market_validation_promotes_all_answer_layers():
    content = _qa_content(_ui_event_10())

    assert len(content["official_facts"]) == 3
    assert len(content["calculated_facts"]) == 9
    assert content["research_inferences"]
    assert content["refusal_boundaries"]


def test_market_validation_projection_keeps_industry_scope_and_facts():
    config = read_json(CONFIG_PATH)
    project_root = resolve_project_root(CONFIG_PATH, config)
    source, _ = load_source_bundle(project_root, config)
    ui_reference, _ = load_ui_reference_bundle(project_root, config)
    events = build_unified_events(source, config["dataset_version"], ui_reference=ui_reference)
    samples = project_sft_samples([event for event in events if event["event_id"] == "event-10"])
    sample = next(row for row in samples if row["sample_id"] == "event-10-qa-qa-event-10-market-validation")

    assert len(sample["metadata"]["related_industry_ids"]) == 9
    assert len(sample["metadata"]["research_content"]["calculated_facts"]) == 9
    assert "美国白宫" in sample["messages"][2]["content"]
    assert "行情验证" in sample["messages"][2]["content"]
    assert "T0 -1.89%" in sample["messages"][2]["content"]
    assert "未提供可用计算事实" not in sample["messages"][2]["content"]
    assert "未找到可直接核验的官方事实" not in sample["messages"][2]["content"]


def test_validation_rejects_disconnected_market_validation_content():
    dataset_path = TRAINING_ROOT / "data" / "sft_dataset.jsonl"
    sample = next(
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if json.loads(line).get("sample_id") == "event-10-qa-qa-event-10-market-validation"
    )

    broken = deepcopy(sample)
    broken["metadata"]["research_content"]["official_facts"] = []
    broken["metadata"]["research_content"]["calculated_facts"] = []
    broken["metadata"]["related_industry_ids"] = []
    codes = {error["code"] for error in _check(broken)}
    assert {
        "CONTENT_QA_OFFICIAL_FACTS_MISSING",
        "CONTENT_QA_CALCULATED_FACTS_MISSING",
        "CONTENT_QA_SCOPE_MISSING",
    } <= codes
