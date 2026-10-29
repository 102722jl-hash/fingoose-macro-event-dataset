from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


WINDOW_KEYS = ("T_MINUS_1", "T0", "D1", "D3", "D5", "D20")
HORIZON_KEYS = ("IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM")


def _answers() -> dict[tuple[str, str], dict]:
    from fingoose_qa_reasoning_v2 import build_qa_records

    return {
        (row["event_id"], row["task_type"]): row
        for row in build_qa_records(ROOT).answers
    }


def test_evidence_audit_directly_classifies_every_conclusion_type() -> None:
    answers = _answers()
    for event_index in range(1, 11):
        event_id = f"event-{event_index:02d}"
        answer = answers[(event_id, "EVIDENCE_AUDIT")]
        task = answer["task_answer"]
        assert task["answer_type"] == "EVIDENCE_AUDIT"
        assert all(
            label in task["direct_answer_zh"]
            for label in ("官方事实", "研究推断", "计算事实", "拒答")
        )
        assert len(task["official_facts"]) == len(answer["evidence"])
        assert task["research_inferences"]
        assert len(task["calculated_facts"]) == len(answer["market_windows"])
        assert len(task["refusal_boundaries"]) == len(answer["refusals"])
        for fact in task["official_facts"]:
            assert fact["fact_zh"]
            assert fact["original_quote"]
            assert fact["locator_zh"]
            assert fact["source_url"].startswith(("http://", "https://"))


def test_market_validation_returns_six_windows_and_horizon_verdicts() -> None:
    answers = _answers()
    allowed = {"SUPPORTS", "WEAKENS", "INDISTINGUISHABLE", "DATA_MISSING"}
    for event_index in range(1, 11):
        event_id = f"event-{event_index:02d}"
        answer = answers[(event_id, "MARKET_VALIDATION")]
        task = answer["task_answer"]
        assert task["answer_type"] == "MARKET_VALIDATION"
        assert "行业收益" in task["method_zh"]
        assert "沪深300收益" in task["method_zh"]
        assert "相对收益" in task["method_zh"]
        assert len(task["industry_results"]) == len(answer["industry_impacts"])
        for result in task["industry_results"]:
            assert tuple(result["windows"]) == WINDOW_KEYS
            assert set(result["horizon_verdicts"]) == set(HORIZON_KEYS)
            assert result["overall_verdict"] in allowed
            for point in result["windows"].values():
                assert set(point) >= {
                    "actual_date",
                    "industry_return",
                    "market_return",
                    "market_relative_return",
                }
            for verdict in result["horizon_verdicts"].values():
                assert verdict["verdict"] in allowed
                assert verdict["verdict_zh"] in {
                    "支持",
                    "削弱",
                    "无法区分",
                    "数据缺失",
                }
                assert verdict["basis_zh"]


def test_market_validation_event_07_respects_post_cutoff_anchor() -> None:
    task = _answers()[("event-07", "MARKET_VALIDATION")]["task_answer"]
    assert task["cutoff_blocked"] is True
    assert all(
        row["overall_verdict"] == "INDISTINGUISHABLE"
        for row in task["industry_results"]
    )
    assert "晚于截止日" in task["direct_answer_zh"]


def test_industry_company_answers_each_named_company_with_required_evidence() -> None:
    answers = _answers()
    for event_index in range(1, 11):
        event_id = f"event-{event_index:02d}"
        answer = answers[(event_id, "INDUSTRY_COMPANY")]
        task = answer["task_answer"]
        assert task["answer_type"] == "INDUSTRY_COMPANY"
        assert len(task["company_results"]) == 3
        assert all(row["company_name"] in task["direct_answer_zh"] for row in task["company_results"])
        for result in task["company_results"]:
            assert result["pre_event_disclosures"]
            assert result["mechanism_zh"]
            assert set(result["directions_zh"]) == set(HORIZON_KEYS)
            assert result["conditions_zh"]
            assert result["invalidation_conditions_zh"]
            assert result["counterevidence"] or result["counterevidence_search_zh"]
            assert result["trading_status_zh"]
            assert result["suspension_status_zh"]
            assert result["decision_zh"]
            for evidence in result["pre_event_disclosures"]:
                assert evidence["published_at"] <= answer["prediction_cutoff_at"][:10]
                assert evidence["original_quote"]
                assert evidence["source_url"].startswith(("http://", "https://"))


def test_event_01_company_answer_contains_actual_exposure_and_confounder() -> None:
    task = _answers()[("event-01", "INDUSTRY_COMPANY")]["task_answer"]
    by_name = {row["company_name"]: row for row in task["company_results"]}
    assert "分子诊断" in by_name["达安基因"]["pre_event_disclosures"][0]["original_quote"]
    assert "航空" in by_name["上海机场"]["pre_event_disclosures"][0]["original_quote"]
    assert any("融资券" in row["title_zh"] for row in by_name["中国国航"]["confounders"])
    assert by_name["中国国航"]["trading_status_zh"] == "正常交易已核验"


def test_specialized_tabs_have_distinct_ui_renderers() -> None:
    from fingoose_company_impact_qa_ui_v2 import build_ui_bundle, render_workbench

    html = render_workbench(
        build_ui_bundle(
            ROOT,
            qa_root=ROOT / "work/qa_reasoning_pilot_v2_candidate",
        )
    )
    for name in (
        "qaEvidenceAuditAnswer",
        "qaMarketValidationAnswer",
        "qaIndustryCompanyAnswer",
    ):
        assert name in html
    for label in (
        "结论分类",
        "阶段判定",
        "行业收益",
        "沪深300收益",
        "事件前业务披露",
        "限制与失效条件",
        "反证与独立混杂",
        "停复牌核验",
    ):
        assert label in html
