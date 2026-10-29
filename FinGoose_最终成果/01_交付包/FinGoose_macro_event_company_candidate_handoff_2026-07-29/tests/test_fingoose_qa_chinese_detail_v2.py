from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


RAW_ENUMS = {
    "POSITIVE",
    "NEGATIVE",
    "MIXED",
    "UNKNOWN",
    "CORE_DIRECT",
    "SECOND_ORDER",
    "CONDITIONAL",
}


def _main_answers() -> list[dict]:
    from fingoose_qa_reasoning_v2 import build_qa_records

    return [
        row
        for row in build_qa_records(ROOT).answers
        if row["task_type"] == "MAIN_REASONING"
    ]


def test_all_public_evidence_has_chinese_fact_and_audit_original() -> None:
    answers = _main_answers()
    evidence = {
        row["evidence_id"]: row
        for answer in answers
        for row in answer["evidence"]
    }
    assert len(evidence) == 46
    for row in evidence.values():
        assert row["publisher_zh"]
        assert row["fact_zh"]
        assert row["locator_zh"]
        assert row["original_quote"]
        assert row["translation_note_zh"] == "中文释义，英文原文保留用于审计"


def test_industry_impacts_explain_each_horizon_in_concrete_chinese() -> None:
    for answer in _main_answers():
        assert set(answer["horizon_summary_zh"]) == {
            "IMMEDIATE",
            "SHORT_TERM",
            "MEDIUM_TERM",
        }
        for summary in answer["horizon_summary_zh"].values():
            assert "个行业" in summary
            assert not any(token in summary for token in RAW_ENUMS)
        for impact in answer["industry_impacts"]:
            assert impact["impact_tier_zh"] in {
                "直接影响",
                "二阶传导",
                "条件性影响",
            }
            details = impact["horizon_details"]
            assert set(details) == {"IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM"}
            for key, detail in details.items():
                assert detail["horizon_zh"] in {"即时", "短期", "中期"}
                assert detail["direction_zh"] in {"正向", "负向", "分化", "未知"}
                assert impact["observable_driver_zh"] in detail["detail_zh"]
                assert impact["industry_operating_variable_zh"] in detail["detail_zh"]
                assert impact["industry_financial_variable_zh"] in detail["detail_zh"]
                assert not any(token in detail["detail_zh"] for token in RAW_ENUMS)


def test_mechanism_nodes_and_research_summary_are_chinese_and_specific() -> None:
    for answer in _main_answers():
        assert answer["research_conclusion_zh"]
        assert "直接影响" in answer["research_conclusion_zh"]
        assert "即时" in answer["research_conclusion_zh"]
        assert "短期" in answer["research_conclusion_zh"]
        assert "中期" in answer["research_conclusion_zh"]
        for node in answer["mechanism_chain"]:
            assert node["node_type_zh"]
            assert node["node_type_zh"] != node["node_type"]


def test_ui_renders_chinese_research_detail_and_collapsible_audit_original() -> None:
    from fingoose_company_impact_qa_ui_v2 import build_ui_bundle, render_workbench

    qa_root = ROOT / "work/qa_reasoning_pilot_v2_candidate"
    html = render_workbench(build_ui_bundle(ROOT, qa_root=qa_root))
    for text in (
        "中文事实摘录",
        "审计原文",
        "可观察驱动",
        "经营变量",
        "财务变量",
        "成立条件",
        "失效条件",
        "直接影响",
        "二阶传导",
        "条件性影响",
    ):
        assert text in html
    assert "directionLabelZh" in html
    assert "tierLabelZh" in html


def test_public_serialization_does_not_expose_hidden_labels() -> None:
    serialized = json.dumps(_main_answers(), ensure_ascii=False)
    assert "expected_evidence_ids" not in serialized
    assert "hard_failure_labels" not in serialized
