from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))
CANDIDATE = ROOT / "work/company_impact_high_quality_v2_candidate"


class CompanyConfounderClosureIntegrationTests(unittest.TestCase):
    def test_unresolved_grade_or_search_keeps_completion_open(self) -> None:
        from fingoose_company_candidate_completion_v2 import evaluate_completion

        common = {
            "mapping_id": "mapping-1",
            "binding_review": {"binding_selection_complete": True},
            "dossier": {
                "research_categories": [
                    {
                        "category": category,
                        "status": "EVIDENCE_SUPPORTED",
                        "evidence_ids": ["evidence-1"],
                    }
                    for category in {
                        "BUSINESS_STRUCTURE",
                        "GEOGRAPHIC_EXPOSURE",
                        "DEMAND_SENSITIVITY",
                        "COST_SENSITIVITY",
                        "LIMITATIONS_AND_COUNTEREVIDENCE",
                    }
                ]
            },
            "direction": {
                "horizon_reviews": {
                    horizon: {"decision_status": "DIRECTIONAL_CANDIDATE"}
                    for horizon in {"IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM"}
                }
            },
            "market_window": {
                "observations": {
                    window: {"status": "OBSERVED"}
                    for window in {"T_MINUS_1", "T0", "D1", "D3", "D5", "D20"}
                }
            },
            "relative_window": {
                "industry_benchmark_id": "SW1-801010",
                "observations": {
                    window: {
                        "industry_status": "AVAILABLE",
                        "industry_relative_return": 0.01,
                    }
                    for window in {"T_MINUS_1", "T0", "D1", "D3", "D5", "D20"}
                },
            },
            "mechanism_chain": {
                "nodes": [
                    {"node_id": f"n{index}", "node_type": node_type}
                    for index, node_type in enumerate(
                        (
                            "EVENT_FACT",
                            "BEHAVIOR_OR_POLICY_CHANGE",
                            "OBSERVABLE_OPERATING_VARIABLE",
                            "INDUSTRY_REVENUE_OR_COST_VARIABLE",
                            "COMPANY_BUSINESS_EXPOSURE",
                            "DIRECTION_ASSESSMENT",
                            "PRICE_AND_CONFOUNDER_VERIFICATION",
                        )
                    )
                ],
                "edges": [
                    {"from_node_id": f"n{index}", "to_node_id": f"n{index + 1}"}
                    for index in range(6)
                ],
            },
        }
        unresolved = evaluate_completion(
            **common,
            confounder={
                "company_confounder_status": "REVIEWED",
                "overall_grade": "UNRESOLVED",
                "search_status": "COMPLETE",
                "suspension_status": "VERIFIED_TRADING",
            },
        )
        incomplete_search = evaluate_completion(
            **common,
            confounder={
                "company_confounder_status": "REVIEWED",
                "overall_grade": "CLEAN",
                "search_status": "INCOMPLETE",
                "suspension_status": "VERIFIED_TRADING",
            },
        )

        self.assertIn("CONFOUNDER_GRADE_UNRESOLVED", unresolved["blockers"])
        self.assertIn("CONFOUNDER_SEARCH_INCOMPLETE", incomplete_search["blockers"])

    def test_ui_bundle_exposes_complete_confounder_lineage(self) -> None:
        from fingoose_company_impact_ui_v2 import build_ui_bundle, render_workbench

        bundle = build_ui_bundle(ROOT, candidate_root=CANDIDATE)
        companies = [company for event in bundle["events"] for company in event["companies"]]

        self.assertEqual(len(companies), 30)
        for company in companies:
            self.assertTrue(company["confounder_argument"]["argument_zh"])
            self.assertTrue(company["confounder_search_audit"]["search_audit_id"])
            self.assertTrue(company["trading_status_review"]["trading_review_id"])
            self.assertTrue(company["counterevidence_review"]["counterevidence_review_id"])
            self.assertIsInstance(company["announcement_body_reviews"], list)

        html = render_workbench(bundle)
        self.assertIn("argument_zh", html)
        self.assertIn("body_locator", html)
        self.assertIn("affected_windows", html)
        self.assertIn("trading_status_review", html)
        self.assertIn("confounder_search_audit", html)
        self.assertNotIn(
            "公告标题检索未发现高风险候选，正文检索与公司级反证仍待完成",
            html,
        )


if __name__ == "__main__":
    unittest.main()
