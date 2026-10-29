import tempfile
import unittest
from pathlib import Path

from fingoose_event_industry_impact_v1 import (
    build_event_industry_candidates,
    write_event_industry_bundle,
)


class EventIndustryImpactTests(unittest.TestCase):
    def setUp(self):
        self.anchors = [
            {
                "anchor_id": "anchor-causal",
                "event_id": "event-01",
                "milestone_id": "milestone-causal",
                "activation_mode": "CAUSAL_CANDIDATE",
                "evidence_status": "VERIFIED_EXISTING",
                "impact_tags": ["GLOBAL_DEMAND"],
                "fact": "A causal candidate fact.",
            },
            {
                "anchor_id": "anchor-observation",
                "event_id": "event-01",
                "milestone_id": "milestone-observation",
                "activation_mode": "OBSERVATION_ONLY",
                "evidence_status": "VERIFIED_EXISTING",
                "impact_tags": ["RISK_APPETITE"],
                "fact": "An observation only fact.",
            },
        ]
        self.graphs = [{
            "event_id": "event-01",
            "graph_id": "graph-01",
            "nodes": [
                {"node_id": "shock", "layer": "shock", "label": "Shock"},
                {"node_id": "channel-demand", "layer": "channel", "label": "GLOBAL_DEMAND"},
                {"node_id": "asset", "layer": "asset", "label": "S&P 500"},
            ],
            "edges": [
                {
                    "edge_id": "edge-causal",
                    "anchor_milestone_id": "milestone-causal",
                    "from_node_id": "shock",
                    "to_node_id": "channel-demand",
                    "status": "PROPOSED",
                    "expected_path": {"IMMEDIATE": "DOWN", "SHORT_TERM": "DOWN", "MEDIUM_TERM": "UNKNOWN"},
                    "conditions": ["Demand channel remains active."],
                    "invalidation_conditions": ["Official correction."],
                    "counterevidence": ["Policy offset."],
                }
            ],
        }]
        self.companies = [
            {
                "event_id": "event-01", "company_code": "600001.SH", "company_name": "甲公司",
                "industry": "交通运输", "industry_status": "MAPPED", "official_company_exposure_verified": False,
            },
            {
                "event_id": "event-01", "company_code": "600002.SH", "company_name": "乙公司",
                "industry": "交通运输", "industry_status": "MAPPED", "official_company_exposure_verified": False,
            },
        ]
        self.ratings = [
            {"event_id": "event-01", "company_code": "600001.SH", "status": "WINDOW_DATA_AVAILABLE"},
            {"event_id": "event-01", "company_code": "600002.SH", "status": "NO_WINDOW_DATA"},
        ]
        self.financials = [
            {
                "event_id": "event-01", "company_code": "600001.SH",
                "BALANCE_SHEET": {"status": "PRE_EVENT_DATA_AVAILABLE"},
                "INCOME_STATEMENT": {"status": "NO_PRE_EVENT_DATA"},
                "CASH_FLOW": {"status": "NO_PRE_EVENT_DATA"},
            },
            {
                "event_id": "event-01", "company_code": "600002.SH",
                "BALANCE_SHEET": {"status": "NO_PRE_EVENT_DATA"},
                "INCOME_STATEMENT": {"status": "NO_PRE_EVENT_DATA"},
                "CASH_FLOW": {"status": "NO_PRE_EVENT_DATA"},
            },
        ]

    def test_groups_companies_by_anchor_and_industry_with_support_states(self):
        rows = build_event_industry_candidates(
            self.anchors, self.graphs, self.companies, self.ratings, self.financials
        )
        self.assertEqual(len(rows), 2)
        causal = next(row for row in rows if row["anchor_id"] == "anchor-causal")
        self.assertEqual(causal["industry"], "交通运输")
        self.assertEqual(len(causal["companies"]), 2)
        self.assertEqual(causal["companies"][0]["rating_support_status"], "WINDOW_DATA_AVAILABLE")
        self.assertEqual(causal["companies"][0]["financial_support_status"], "PRE_EVENT_DATA_AVAILABLE")
        self.assertEqual(causal["channels"], ["GLOBAL_DEMAND"])

    def test_only_causal_anchor_with_proposed_edges_has_conditional_direction(self):
        rows = build_event_industry_candidates(
            self.anchors, self.graphs, self.companies, self.ratings, self.financials
        )
        causal = next(row for row in rows if row["anchor_id"] == "anchor-causal")
        observation = next(row for row in rows if row["anchor_id"] == "anchor-observation")
        self.assertEqual(causal["direction_status"], "PROPOSED_CONDITIONAL")
        self.assertEqual(causal["expected_industry_direction"], "UNKNOWN")
        self.assertEqual(observation["direction_status"], "UNKNOWN")
        self.assertEqual(observation["transmission_edges"], [])
        self.assertFalse(causal["official_company_exposure_verified"])
        self.assertFalse(causal["causal_attribution_allowed"])

    def test_bundle_keeps_candidate_release_boundary(self):
        rows = build_event_industry_candidates(
            self.anchors, self.graphs, self.companies, self.ratings, self.financials
        )
        with tempfile.TemporaryDirectory(dir=Path("C:/tmp")) as temp:
            manifest = write_event_industry_bundle(Path(temp) / "bundle", rows)
            self.assertFalse(manifest["formal_ready"])
            self.assertTrue(all(item["sha256"] for item in manifest["files"]))


if __name__ == "__main__":
    unittest.main()
