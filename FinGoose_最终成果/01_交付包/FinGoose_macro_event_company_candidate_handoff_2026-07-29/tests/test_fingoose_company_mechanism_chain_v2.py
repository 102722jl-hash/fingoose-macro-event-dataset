from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


NODE_TYPES = (
    "EVENT_FACT",
    "BEHAVIOR_OR_POLICY_CHANGE",
    "OBSERVABLE_OPERATING_VARIABLE",
    "INDUSTRY_REVENUE_OR_COST_VARIABLE",
    "COMPANY_BUSINESS_EXPOSURE",
    "DIRECTION_ASSESSMENT",
    "PRICE_AND_CONFOUNDER_VERIFICATION",
)


class CompanyMechanismChainTests(unittest.TestCase):
    def _chain(self) -> dict:
        from fingoose_company_mechanism_chain_v2 import build_mechanism_chain

        return build_mechanism_chain(
            {
                "mapping_id": "mapping-1",
                "event_id": "event-01",
                "anchor_id": "anchor-1",
                "company_id": "company-1",
                "company_code": "002030.SZ",
                "company_name": "达安基因",
            },
            {
                "mapping_id": "mapping-1",
                "behavior_or_policy_change": "公共卫生响应提升核酸筛查与试剂准入需求。",
                "observable_operating_variable": "核酸检测需求与试剂准入进度。",
                "industry_revenue_or_cost_variable": "分子诊断试剂销量与单位收入。",
                "company_business_exposure": "公司核酸检测试剂业务直接暴露于检测需求。",
                "direction_assessment": "需求兑现方向偏正，但取决于产品准入。",
                "price_and_confounder_verification": "核对事件窗口收益、停复牌和公司公告混杂。",
                "direction": "MIXED",
                "decision_status": "DIRECTIONAL_CANDIDATE",
                "horizon_directions": {
                    "IMMEDIATE": "MIXED",
                    "SHORT_TERM": "POSITIVE",
                    "MEDIUM_TERM": "MIXED",
                },
                "conditions": ["???????????????"],
                "invalidation_conditions": ["?????????"],
                "operating_metrics": [
                    {"name": "??????", "unit": "????"},
                    {"name": "????", "unit": "?????"},
                ],
                "company_evidence_ids": ["company-evidence-1"],
            },
            binding_review={"primary_binding_id": "binding-1"},
            company_evidence=[
                {"evidence_id": "company-evidence-1", "company_id": "company-1"}
            ],
            direction_assessment={"direction_id": "direction-1"},
            market_window={"company_market_window_id": "market-window-1"},
            relative_window={"relative_window_id": "relative-window-1"},
            confounder={"company_confounder_id": "confounder-1"},
            timeline_node={
                "fast_node_id": "fast-event-01-M04",
                "event_id": "event-01",
                "fact": "WHO 将疫情定性为全球大流行。",
                "source_ids": ["timeline-source-1"],
            },
        )

    def test_builds_ordered_seven_layer_company_chain(self) -> None:
        chain = self._chain()

        self.assertEqual([node["node_type"] for node in chain["nodes"]], list(NODE_TYPES))
        self.assertEqual(len(chain["edges"]), 6)
        self.assertEqual(
            [(edge["from_node_id"], edge["to_node_id"]) for edge in chain["edges"]],
            [
                (chain["nodes"][index]["node_id"], chain["nodes"][index + 1]["node_id"])
                for index in range(6)
            ],
        )
        self.assertEqual(chain["chain_status"], "PROPOSED_COMPANY_MECHANISM")
        self.assertEqual(chain["review_status"], "NEEDS_HUMAN_REVIEW")
        self.assertFalse(chain["formal_ready"])
        self.assertEqual(chain["sha_gate"], "DEFERRED")
        self.assertFalse(chain["price_selection_used"])
        self.assertEqual(
            chain["horizon_directions"],
            {"IMMEDIATE": "MIXED", "SHORT_TERM": "POSITIVE", "MEDIUM_TERM": "MIXED"},
        )
        self.assertEqual(chain["conditions"], ["???????????????"])
        self.assertEqual(chain["invalidation_conditions"], ["?????????"])
        self.assertEqual(chain["operating_metrics"][0]["unit"], "????")

    def test_keeps_event_company_and_verification_evidence_scoped(self) -> None:
        chain = self._chain()
        nodes = {node["node_type"]: node for node in chain["nodes"]}

        self.assertEqual(nodes["EVENT_FACT"]["evidence_ids"], ["timeline-source-1"])
        self.assertEqual(
            nodes["COMPANY_BUSINESS_EXPOSURE"]["evidence_ids"],
            ["company-evidence-1"],
        )
        self.assertEqual(
            nodes["PRICE_AND_CONFOUNDER_VERIFICATION"]["evidence_ids"],
            ["market-window-1", "relative-window-1", "confounder-1"],
        )
        self.assertTrue(
            set(nodes["EVENT_FACT"]["evidence_ids"]).isdisjoint(
                nodes["COMPANY_BUSINESS_EXPOSURE"]["evidence_ids"]
            )
        )
        all_text = " ".join(node["statement"] for node in chain["nodes"])
        for forbidden in ("DCOILWTICO", "DCOILBRENTEU", "SP500", "DEXCHUS", "VIXCLS"):
            self.assertNotIn(forbidden, all_text)

    def test_completion_rejects_missing_layer_and_broken_edge(self) -> None:
        from fingoose_company_candidate_completion_v2 import evaluate_completion

        chain = self._chain()
        complete_inputs = {
            "mapping_id": "mapping-1",
            "binding_review": {"binding_selection_complete": True},
            "dossier": {
                "research_categories": [
                    {"category": category, "status": "EVIDENCE_SUPPORTED", "evidence_ids": ["e-1"]}
                    for category in (
                        "BUSINESS_STRUCTURE",
                        "GEOGRAPHIC_EXPOSURE",
                        "DEMAND_SENSITIVITY",
                        "COST_SENSITIVITY",
                        "LIMITATIONS_AND_COUNTEREVIDENCE",
                    )
                ]
            },
            "direction": {
                "horizon_reviews": {
                    horizon: {"decision_status": "DIRECTIONAL_CANDIDATE"}
                    for horizon in ("IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM")
                }
            },
            "market_window": {
                "observations": {
                    window: {"status": "OBSERVED"}
                    for window in ("T_MINUS_1", "T0", "D1", "D3", "D5", "D20")
                }
            },
            "relative_window": {
                "industry_benchmark_id": "industry-1",
                "observations": {
                    window: {"industry_status": "AVAILABLE", "industry_relative_return": 0.0}
                    for window in ("T_MINUS_1", "T0", "D1", "D3", "D5", "D20")
                },
            },
            "confounder": {
                "company_confounder_status": "REVIEWED",
                "suspension_status": "VERIFIED_TRADING",
            },
        }

        for mutation in ("missing_node", "broken_edge"):
            with self.subTest(mutation=mutation):
                incomplete = copy.deepcopy(chain)
                if mutation == "missing_node":
                    incomplete["nodes"].pop(3)
                else:
                    incomplete["edges"][2]["to_node_id"] = incomplete["nodes"][5]["node_id"]
                result = evaluate_completion(mechanism_chain=incomplete, **complete_inputs)
                self.assertIn("MECHANISM_CHAIN_INCOMPLETE", result["blockers"])


if __name__ == "__main__":
    unittest.main()
