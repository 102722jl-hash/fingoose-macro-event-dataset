from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


class IndustryImpactUiV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from fingoose_company_impact_io_v2 import read_jsonl
        from fingoose_company_impact_ui_v2 import build_ui_bundle, render_workbench
        from fingoose_event_01_industry_closure_v2 import (
            build_event_01_closure_bundle,
        )

        registry = read_jsonl(
            ROOT / "configs/industry_impact_v2/event_01_source_registry.jsonl"
        )
        evidence_fetches = [
            {
                **row,
                "accessed_at": "2026-08-04T12:00:00+08:00",
                "verified_quote": row["required_quote"],
                "raw_snapshot_path": f"raw/evidence/{row['source_id']}.html",
                "fetch_status": "RETRIEVED_QUOTE_VERIFIED",
                "failure_reason": None,
            }
            for row in registry
        ]
        cls.overlay_root = ROOT / "work/_test_event01_ui_overlay"
        build_event_01_closure_bundle(
            ROOT,
            output_root=cls.overlay_root,
            evidence_fetches=evidence_fetches,
            market_payloads={},
        )
        cls.bundle = build_ui_bundle(
            ROOT,
            candidate_root=ROOT / "work/company_impact_high_quality_v2_candidate",
            industry_root=ROOT / "work/industry_impact_high_quality_v2_candidate",
            industry_overlay_root=cls.overlay_root,
        )
        cls.html = render_workbench(cls.bundle)

    def test_event_projection_contains_independent_industry_layer(self) -> None:
        event_01 = next(
            row for row in self.bundle["events"] if row["event_id"] == "event-01"
        )
        self.assertEqual(len(event_01["industry_impacts"]), 8)
        self.assertEqual(len(event_01["industry_mechanism_chains"]), 8)
        self.assertEqual(
            {row["impact_tier"] for row in event_01["industry_impacts"]},
            {"CORE_DIRECT", "SECOND_ORDER", "CONDITIONAL"},
        )
        self.assertTrue(
            all(
                len(row["nodes"]) == 7
                for row in event_01["industry_mechanism_chains"]
            )
        )
        self.assertTrue(
            all(
                row.get("overlay_source") == "EVENT_01_CLOSURE"
                for row in event_01["industry_impacts"]
            )
        )

    def test_overlay_replaces_only_event_01_rows(self) -> None:
        event_02 = next(
            row for row in self.bundle["events"] if row["event_id"] == "event-02"
        )
        self.assertTrue(
            all(
                row.get("overlay_source") is None
                for row in event_02["industry_impacts"]
            )
        )

    def test_industry_layer_links_without_changing_company_count(self) -> None:
        event_01 = next(
            row for row in self.bundle["events"] if row["event_id"] == "event-01"
        )
        self.assertEqual(len(event_01["companies"]), 3)
        transport = next(
            row
            for row in event_01["industry_impacts"]
            if row["display_name_zh"] == "交通运输"
        )
        self.assertEqual(transport["company_count"], 2)
        self.assertEqual(len(transport["company_links"]), 2)

    def test_workbench_renders_tiers_industry_chain_and_detail(self) -> None:
        for text in (
            "行业板块链",
            "直接影响",
            "二阶传导",
            "条件性影响",
            "行业影响详情",
            "T-20 至 D20",
            "驱动变量",
            "数据库可用性审计",
            "公司样本待补",
        ):
            self.assertIn(text, self.html)
        self.assertIn("state.industryMappingId", self.html)
        self.assertIn("data-industry-tier", self.html)
        self.assertIn("data-industry-mapping", self.html)

    def test_industry_detail_renders_node_sources_driver_and_confounders(self) -> None:
        for text in (
            "来源事实",
            "计算事实",
            "研究推断",
            "查看原文",
            "主驱动（右轴）",
            "竞争解释",
            "混杂分析",
            "区分检验",
            "混杂证据待核验",
            "归因边界",
            "挑战集",
            "原始值",
            "归一化值",
        ):
            self.assertIn(text, self.html)

    def test_all_event_industry_branches_have_frozen_counts(self) -> None:
        expected = {
            "event-01": 8,
            "event-02": 8,
            "event-03": 8,
            "event-04": 8,
            "event-05": 7,
            "event-06": 7,
            "event-07": 7,
            "event-08": 7,
            "event-09": 8,
            "event-10": 9,
        }
        actual = {
            event["event_id"]: len(event["industry_impacts"])
            for event in self.bundle["events"]
        }
        self.assertEqual(actual, expected)

    def test_all_industry_branches_remain_visible_after_selection(self) -> None:
        self.assertNotIn(
            "if(state.industryMappingId)rows=rows.filter",
            self.html,
        )
        self.assertNotIn(
            "else rows=rows.filter(function(row){return row.impact_tier===state.industryTier})",
            self.html,
        )
        for text in (
            "industry-tier-group",
            "机制证据",
            "驱动数据",
            "行情窗口",
            "公司样本",
        ):
            self.assertIn(text, self.html)

    def test_default_ui_merges_event_01_and_multi_event_overlays(self) -> None:
        from fingoose_company_impact_ui_v2 import build_ui_bundle, render_workbench

        bundle = build_ui_bundle(
            ROOT,
            candidate_root=ROOT / "work/company_impact_high_quality_v2_candidate",
            industry_root=ROOT / "work/industry_impact_high_quality_v2_candidate",
        )
        event_01 = next(row for row in bundle["events"] if row["event_id"] == "event-01")
        event_02 = next(row for row in bundle["events"] if row["event_id"] == "event-02")
        self.assertEqual(len(event_01["industry_impacts"]), 8)
        self.assertEqual(len(event_02["industry_impacts"]), 8)
        self.assertTrue(
            all(
                row.get("overlay_source") == "EVENT_01_CLOSURE"
                for row in event_01["industry_impacts"]
            )
        )
        self.assertTrue(
            all(
                row.get("overlay_source") == "EVENT_02_10_CLOSURE"
                for row in event_02["industry_impacts"]
            )
        )
        self.assertTrue(
            all(
                row.get("market_window", {}).get("window_status") == "AVAILABLE"
                for row in event_02["industry_impacts"]
            )
        )
        html = render_workbench(bundle)
        self.assertIn("Array.isArray(continuous)", html)
        self.assertIn("statement_class", html)
        self.assertIn("event-02-10-industry-closure-v2-candidate", html)
    def test_driver_selection_basis_is_localized_for_research_view(self) -> None:
        self.assertIn(
            "经营驱动在事件前预先登记，未按事后价格表现选择",
            self.html,
        )


if __name__ == "__main__":
    unittest.main()
