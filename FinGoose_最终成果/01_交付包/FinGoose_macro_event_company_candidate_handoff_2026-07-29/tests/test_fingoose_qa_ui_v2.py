from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


QA_ROOT = ROOT / "work/qa_reasoning_pilot_v2_candidate"


def test_ui_bundle_attaches_four_public_answers_per_event() -> None:
    from fingoose_company_impact_qa_ui_v2 import build_ui_bundle

    bundle = build_ui_bundle(ROOT, qa_root=QA_ROOT)
    assert all(len(event["qa"]) == 4 for event in bundle["events"])
    assert bundle["summary"]["qa_case_count"] == 40
    serialized = json.dumps(bundle, ensure_ascii=False)
    assert "expected_evidence_ids" not in serialized
    assert "hard_failure_labels" not in serialized


def test_qa_precedes_original_research_sections() -> None:
    from fingoose_company_impact_qa_ui_v2 import build_ui_bundle, render_workbench

    html = render_workbench(build_ui_bundle(ROOT, qa_root=QA_ROOT))
    assert html.index("研究问答") < html.index("事件时间线")
    assert html.index("事件时间线") < html.index("动态传导链")
    assert html.index("动态传导链") < html.index("行业影响")
    assert html.index("行业影响") < html.index("公司影响")
    assert all(
        label in html for label in ("综合研判", "证据核查", "行情验证", "行业—公司")
    )
    assert "data-qa-task" in html
    assert "data-qa-jump" in html
    assert 'id="qa"' in html


def test_qa_ui_retains_original_workbench_content_and_candidate_state() -> None:
    from fingoose_company_impact_qa_ui_v2 import build_ui_bundle, render_workbench

    html = render_workbench(build_ui_bundle(ROOT, qa_root=QA_ROOT))
    for text in (
        "事件概览",
        "事件时间线",
        "动态传导链",
        "行业影响",
        "公司影响",
        "七步",
        "沪深300",
        "混杂",
        "formal_ready=false",
        "DEFERRED",
    ):
        assert text in html
    assert "evaluator_only" not in html
