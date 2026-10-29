import copy
import json
import sys
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_ROOT.parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from src.io_utils import read_jsonl
from src.market import build_market_layers, market_hard_failures


class MarketLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = build_market_layers(
            industry_candidates=read_jsonl(
                PROJECT_ROOT
                / "work"
                / "event_industry_impact_v1_candidate"
                / "event_industry_impact_candidates.jsonl"
            ),
            reviewed_anchors=read_jsonl(PACKAGE_ROOT / "anchor_catalog.jsonl"),
            reviewed_bindings=read_jsonl(PACKAGE_ROOT / "dynamic_edge_bindings.jsonl"),
            company_windows=read_jsonl(
                PROJECT_ROOT
                / "work"
                / "company_price_windows_public_vendor_v1_candidate"
                / "company_price_windows.jsonl"
            ),
            snapshot_root=(
                PROJECT_ROOT
                / "work"
                / "company_price_windows_public_vendor_v1_candidate"
            ),
            confounder_root=PROJECT_ROOT / "work" / "ten_event_rapid_candidate_v2" / "events",
            mysql_audit=json.loads(
                (PACKAGE_ROOT / "config" / "mysql_market_availability_audit.json").read_text(
                    encoding="utf-8"
                )
            ),
        )

    def test_preserves_43_industry_rows_and_72_company_links(self):
        impacts = self.result["industry_impacts"]
        self.assertEqual(43, len(impacts))
        self.assertEqual(72, sum(len(row["companies"]) for row in impacts))
        self.assertEqual(72, self.result["candidate_company_mention_count"])
        self.assertEqual(0, self.result["verified_company_link_count"])

    def test_industry_lineage_references_reviewed_bindings(self):
        known_binding_ids = {
            row["binding_id"] for row in self.result["reviewed_bindings"]
        }
        for row in self.result["industry_impacts"]:
            with self.subTest(impact=row["impact_candidate_id"]):
                self.assertTrue(row["event_node_id"])
                self.assertTrue(row["anchor_id"])
                self.assertTrue(set(row["binding_ids"]) <= known_binding_ids)
                if row["binding_ids"]:
                    self.assertTrue(row["channel_node_ids"])
                    self.assertTrue(row["intermediate_variable_node_ids"])
                    self.assertEqual("GRAPH_LINKED_CANDIDATE", row["lineage_status"])
                else:
                    self.assertEqual("UNLINKED_CANDIDATE", row["lineage_status"])
                self.assertIn("sw1_id", row["industry_classification"])
                self.assertIn("sw2_id", row["industry_classification"])
                self.assertFalse(row["post_event_price_used_for_direction"])
                self.assertFalse(row["causal_attribution_allowed"])
                if row["direction_status"] == "NEEDS_HUMAN_REVIEW":
                    self.assertEqual("UNKNOWN", row["direction_path"]["IMMEDIATE"])

    def test_all_30_company_windows_have_seven_session_observations(self):
        required = {"T_MINUS_20", "T_MINUS_1", "T0", "D1", "D3", "D5", "D20"}
        windows = self.result["company_windows"]
        self.assertEqual(30, len(windows))
        for row in windows:
            with self.subTest(window=row["price_window_id"]):
                self.assertEqual(required, set(row["observations"]))
                self.assertEqual("EXCHANGE_TRADING_SESSIONS", row["calendar_alignment"])
                self.assertEqual("UNVERIFIED", row["suspension_alignment"])
                self.assertEqual("UNKNOWN", row["licence"]["scope"])
                self.assertFalse(row["licence"]["redistribution_allowed"])
                self.assertIn(row["confounding_grade"], {"CLEAN", "MINOR", "MATERIAL", "DOMINANT", "UNRESOLVED"})

    def test_absolute_returns_recompute_and_missing_benchmarks_stay_explicit(self):
        for row in self.result["company_windows"]:
            baseline = row["observations"]["T_MINUS_1"]["close"]
            for horizon, observation in row["observations"].items():
                expected = (observation["close"] / baseline) - 1.0
                self.assertAlmostEqual(expected, observation["absolute_return"], places=12)
                self.assertIsNone(observation["broad_market_relative_return"])
                self.assertIsNone(observation["industry_relative_return"])
                self.assertEqual("UNAVAILABLE", observation["broad_market_benchmark_status"])
                self.assertEqual("UNAVAILABLE", observation["industry_benchmark_status"])
            self.assertEqual(
                "company_return - broad_market_return",
                row["formulas"]["broad_market_relative_return"],
            )

    def test_database_availability_audit_is_logged_without_credentials(self):
        manifest = self.result["mysql_query_manifest"]
        self.assertEqual(1, len(manifest))
        row = manifest[0]
        self.assertEqual("information_schema.tables", row["table"])
        self.assertEqual("READ_ONLY_METADATA_AUDIT", row["query_type"])
        self.assertEqual("EXECUTED", row["execution_status"])
        self.assertFalse(row["credentials_included"])
        self.assertEqual(1, row["row_count"])
        self.assertEqual(64, len(row["result_sha256"]))
        self.assertIn("SELECT TABLE_NAME", row["sql"])
        self.assertEqual(
            "UNVERIFIED_NO_SIGNED_EXECUTION_LOG",
            row["execution_authenticity_status"],
        )


    def test_market_report_failures_are_derived_from_output_content(self):
        self.assertEqual([], market_hard_failures(self.result))

        mutated = copy.deepcopy(self.result)
        mutated["company_windows"][0]["observations"].pop("D20")
        mutated["company_windows"][1]["observations"]["D1"]["absolute_return"] = 99.0
        failures = market_hard_failures(mutated)
        self.assertIn("MISSING_REQUIRED_MARKET_OBSERVATION", failures)
        self.assertIn("NON_RECOMPUTABLE_COMPANY_RETURN", failures)

    def test_market_gate_rederives_lineage_verified_links_and_mysql_audit(self):
        mutated = copy.deepcopy(self.result)
        linked = next(
            row
            for row in mutated["industry_impacts"]
            if row["lineage_status"] == "GRAPH_LINKED_CANDIDATE"
        )
        linked["binding_ids"] = []
        linked["channel_node_ids"] = []
        linked["intermediate_variable_node_ids"] = []
        linked["verified_company_link_count"] = 999
        mutated["verified_company_link_count"] = 999
        mutated["mysql_query_manifest"] = [
            {
                "execution_status": "EXECUTED",
                "credentials_included": False,
                "result_sha256": "0" * 64,
            }
        ]
        failures = market_hard_failures(mutated)
        self.assertIn("BROKEN_GRAPH_LINKED_LINEAGE", failures)
        self.assertIn("UNSUPPORTED_VERIFIED_COMPANY_LINK", failures)
        self.assertIn("MYSQL_AUDIT_INVALID", failures)

    def test_market_gate_validates_anchor_lineage_and_mysql_semantics(self):
        mutated = copy.deepcopy(self.result)
        linked = next(
            row
            for row in mutated["industry_impacts"]
            if row["lineage_status"] == "GRAPH_LINKED_CANDIDATE"
        )
        linked["anchor_id"] = "anchor-fabricated"
        linked["event_node_id"] = "event-99-node-fabricated"
        query = mutated["mysql_query_manifest"][0]
        query["executed_at"] = "fabricated-time"
        query["database"] = "fabricated-database"
        query["a_share_price_table_found"] = True
        failures = market_hard_failures(mutated)
        self.assertIn("BROKEN_GRAPH_LINKED_LINEAGE", failures)
        self.assertIn("MYSQL_AUDIT_INVALID", failures)
if __name__ == "__main__":
    unittest.main()
