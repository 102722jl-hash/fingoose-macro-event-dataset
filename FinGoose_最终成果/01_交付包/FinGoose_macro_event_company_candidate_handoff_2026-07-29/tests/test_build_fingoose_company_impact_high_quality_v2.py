from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


class CompanyImpactBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.output = ROOT / "work" / "_test_company_impact_high_quality_v2"
        if self.output.exists():
            shutil.rmtree(self.output)

    def tearDown(self) -> None:
        if self.output.exists():
            shutil.rmtree(self.output)

    def test_build_emits_expected_cardinality_and_release_boundaries(self) -> None:
        from build_fingoose_company_impact_high_quality_v2 import build
        from fingoose_company_impact_io_v2 import read_jsonl

        report = build(ROOT, self.output)

        self.assertEqual(report["company_count"], 23)
        self.assertEqual(report["event_company_count"], 30)
        self.assertEqual(report["orphan_id_count"], 0)
        self.assertFalse(report["formal_ready"])
        self.assertEqual(report["sha_gate"], "DEFERRED")
        for name in (
            "company_market_windows.jsonl",
            "relative_return_windows.jsonl",
            "event_company_binding_reviews.jsonl",
            "company_dossier_search_audits.jsonl",
            "industry_benchmark_registry.jsonl",
            "candidate_completion_report.jsonl",
            "event_company_mechanism_chains.jsonl",
            "announcement_body_reviews.jsonl",
            "company_confounder_search_audits.jsonl",
            "trading_status_reviews.jsonl",
            "company_counterevidence_reviews.jsonl",
            "company_confounder_arguments.jsonl",
            "company_confounders.jsonl",
        ):
            self.assertTrue((self.output / name).exists(), name)
        self.assertEqual(report.get("mechanism_chain_count"), 30)
        self.assertEqual(report.get("mechanism_chain_node_count"), 210)
        self.assertEqual(report.get("mechanism_chain_edge_count"), 180)
        self.assertEqual(report.get("binding_review_count"), 30)
        self.assertEqual(report.get("completion_report_count"), 30)
        self.assertEqual(report.get("candidate_complete_count"), 0)
        self.assertEqual(report.get("candidate_open_count"), 30)

        relative_rows = read_jsonl(self.output / "relative_return_windows.jsonl")
        self.assertTrue(all(row.get("industry_id") != "UNKNOWN" for row in relative_rows))
        self.assertTrue(all(row.get("industry_benchmark_id") is None for row in relative_rows))
        page = self.output / "ui" / "index.html"
        self.assertTrue(page.exists())
        self.assertEqual(report.get("verified_dossier_count"), 0)
        self.assertEqual(report.get("partial_dossier_count"), 0)
        self.assertEqual(report.get("evidence_complete_candidate_dossier_count"), 23)
        self.assertEqual(report.get("csi300_coverage_count"), 30)
        self.assertEqual(report.get("shenwan_coverage_count"), 0)
        self.assertEqual(report.get("industry_classification_coverage_count"), 30)
        self.assertEqual(report.get("industry_classification_unknown_count"), 0)
        self.assertEqual(
            report.get("industry_classification_status_counts"),
            {"OFFICIAL_HISTORY_ASOF_MATCHED": 30},
        )
        self.assertTrue((self.output / "industry_classification_reviews.jsonl").exists())
        self.assertEqual(report.get("etf_proxy_count"), 0)
        self.assertEqual(report.get("announcement_title_candidate_count"), 47)
        self.assertEqual(report.get("suspension_status_counts"), {"VERIFIED_TRADING": 30})
        self.assertEqual(
            report.get("confounder_grade_counts"),
            {"CLEAN": 15, "MATERIAL": 2, "MINOR": 13},
        )
        self.assertEqual(report.get("ui_path"), "ui/index.html")
        html = page.read_text(encoding="utf-8")
        self.assertIn("事件时间线", html)
        self.assertIn("动态传导链", html)

    def test_ai_reviews_and_hidden_labels_do_not_leak_to_public_bundle(self) -> None:
        from build_fingoose_company_impact_high_quality_v2 import build

        build(ROOT, self.output)
        public = (self.output / "ui" / "ui_data_bundle.js").read_text(encoding="utf-8")

        self.assertNotIn("benchmark_labels", public)
        self.assertNotIn("hidden_label", public)
        self.assertIn("NEEDS_HUMAN_REVIEW", public)

    def test_non_null_relative_returns_recompute(self) -> None:
        from build_fingoose_company_impact_high_quality_v2 import build

        report = build(ROOT, self.output)

        self.assertEqual(report["relative_return_recompute_error_count"], 0)
        self.assertEqual(report["market_relative_observation_count"], 180)


if __name__ == "__main__":
    unittest.main()
