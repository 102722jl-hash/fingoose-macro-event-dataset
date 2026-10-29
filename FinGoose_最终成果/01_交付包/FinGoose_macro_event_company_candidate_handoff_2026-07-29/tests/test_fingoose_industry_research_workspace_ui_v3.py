from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


def test_industry_research_workspace_contains_linkage_and_matrix_contracts() -> None:
    from fingoose_company_impact_qa_ui_v2 import build_ui_bundle, render_workbench

    html = render_workbench(
        build_ui_bundle(ROOT, qa_root=ROOT / "work/qa_reasoning_pilot_v2_candidate")
    )
    for marker in (
        "industryResearchWorkspace",
        "data-closure-evidence-id",
        "data-closure-node-step",
        "closure-evidence-",
        "bindIndustryResearchClosure",
        "industryCompanyMatrix",
        "data-matrix-industry",
        "data-matrix-company",
        "PRETREND",
        "EVENT",
        "SHORT",
        "MEDIUM",
        "七步链证据闭环",
        "标准事件研究",
        "行业—公司联动矩阵",
    ):
        assert marker in html
