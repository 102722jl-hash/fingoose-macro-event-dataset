from __future__ import annotations

import json
from pathlib import Path
import unittest

from fingoose_macro_event_company_deep_dashboard_v1 import (
    COMPANY_NODE_SEQUENCE,
    INDEX_HTML,
    REASONING_SEQUENCE,
    DeepDashboardRepository,
)


ROOT = Path(__file__).resolve().parents[1]
MARKET_ROOT = ROOT / "outputs" / "fingoose_macro_event_attribution_v1"
COMPANY_ROOT = ROOT / "outputs" / "fingoose_macro_event_company_enriched_candidate_v1"


class DeepDashboardRepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repository = DeepDashboardRepository(MARKET_ROOT, COMPANY_ROOT)

    def test_release_counts_and_event_workspace(self) -> None:
        overview = self.repository.overview()
        self.assertEqual(overview["event_count"], 10)
        self.assertEqual(overview["market_sample_count"], 40)
        self.assertEqual(overview["company_dossier_count"], 30)
        self.assertEqual(overview["company_sample_count"], 60)
        self.assertTrue(overview["market_formal_ready"])
        self.assertEqual(overview["company_release_tier"], "CANDIDATE")
        self.assertFalse(overview["company_formal_ready"])
        workspace = self.repository.event_workspace("event-01")
        self.assertEqual(len(workspace["market_samples"]), 4)
        self.assertEqual(len(workspace["companies"]), 3)

    def test_market_sample_preserves_six_steps_and_hides_d20(self) -> None:
        detail = self.repository.market_sample_detail(
            "macro-event-v1-event-01-single-sp500"
        )
        self.assertEqual(
            [step["step_id"] for step in detail["steps"]],
            list(REASONING_SEQUENCE),
        )
        self.assertTrue(all(step["content"] for step in detail["steps"]))
        data_step = detail["steps"][1]["content"]
        self.assertEqual(data_step["visible_window_codes"], ["D1", "D3"])
        visible_text = json.dumps(data_step["market_windows"], ensure_ascii=False)
        self.assertNotIn('"D20"', visible_text)
        self.assertEqual(detail["audit_only"]["outcome"]["outcome_window"], "D20")

    def test_company_detail_preserves_seven_nodes_sources_and_gaps(self) -> None:
        detail = self.repository.company_chain_detail(
            "company-dossier-event-01-600009-sh"
        )
        self.assertEqual(
            [node["node_type"] for node in detail["nodes"]],
            list(COMPANY_NODE_SEQUENCE),
        )
        exposure = detail["nodes"][2]
        self.assertEqual(exposure["value"], "UNKNOWN")
        self.assertEqual(exposure["status"], "PENDING_EVIDENCE")
        self.assertEqual(exposure["sources"], [])
        self.assertTrue(exposure["evidence_gaps"])

    def test_page_contract_has_filters_steps_chain_and_audit_area(self) -> None:
        for token in (
            "event-filter",
            "company-filter",
            "association-filter",
            "direction-filter",
            "evidence-filter",
            "review-filter",
            "market-step-nav",
            "company-chain",
            "evidence-drawer",
            "audit-area",
            "fingoose_macro_event_company_deep_dashboard_v1.js",
        ):
            self.assertIn(token, INDEX_HTML)

    def test_chinese_readability_assets_cover_summary_sources_predictions_and_reviews(self) -> None:
        script = (ROOT / "fingoose_macro_event_company_deep_dashboard_v1.js").read_text(
            encoding="utf-8"
        )
        stylesheet = (ROOT / "fingoose_macro_event_company_deep_dashboard_v1.css").read_text(
            encoding="utf-8"
        )
        for token in (
            "zhText",
            "中文摘要",
            "英文原文",
            "source-link",
            "prediction-hero",
            "company-readable-summary",
            "review-summary",
            "低置信度",
            "强竞争解释",
            "季度累计值差分",
        ):
            self.assertIn(token, script)
        for token in (
            ".source-card",
            ".prediction-hero",
            ".company-readable-summary",
            ".review-summary",
        ):
            self.assertIn(token, stylesheet)


if __name__ == "__main__":
    unittest.main()
