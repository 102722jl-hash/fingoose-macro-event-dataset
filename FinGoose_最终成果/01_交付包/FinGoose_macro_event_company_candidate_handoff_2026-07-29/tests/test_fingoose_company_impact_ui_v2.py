from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


class CompanyImpactUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from build_fingoose_company_candidate_completion_v2 import build
        from fingoose_company_impact_ui_v2 import build_ui_bundle

        cls.candidate = ROOT / ".test-tmp"
        build(ROOT, cls.candidate)
        cls.bundle = build_ui_bundle(ROOT, candidate_root=cls.candidate)

    def test_event_projection_contains_full_company_chain(self) -> None:
        from fingoose_company_impact_ui_v2 import project_event

        event = project_event(self.bundle, "event-02")

        self.assertTrue(event["timeline"])
        self.assertTrue(event["transmission_paths"])
        self.assertTrue(event["industries"])
        self.assertEqual(len(event["companies"]), 3)
        self.assertTrue(all(row["lineage"] for row in event["companies"]))
        self.assertTrue(all(row["market_window"] for row in event["companies"]))
        self.assertTrue(all(row["relative_window"] for row in event["companies"]))
        self.assertTrue(all(row["binding_review"] for row in event["companies"]))
        self.assertTrue(all(row["completion"] for row in event["companies"]))
        self.assertTrue(all(row["mechanism_chain"] for row in event["companies"]))
        self.assertTrue(
            all(len(row["mechanism_chain"]["nodes"]) == 7 for row in event["companies"])
        )
        self.assertTrue(all(row["completion"]["completion_status"] == "OPEN" for row in event["companies"]))
        self.assertEqual(event["summary"]["candidate_open_count"], 3)

    def test_event_01_uses_company_operating_mechanisms(self) -> None:
        from fingoose_company_impact_ui_v2 import project_event

        event = project_event(self.bundle, "event-01")
        by_code = {row["company_code"]: row for row in event["companies"]}

        daan = " ".join(
            node["statement"] for node in by_code["002030.SZ"]["mechanism_chain"]["nodes"]
        )
        airport = " ".join(
            node["statement"] for node in by_code["600009.SH"]["mechanism_chain"]["nodes"]
        )
        airline = " ".join(
            node["statement"] for node in by_code["601111.SH"]["mechanism_chain"]["nodes"]
        )

        self.assertIn("核酸检测", daan)
        self.assertIn("试剂准入", daan)
        self.assertIn("旅客吞吐量", airport)
        self.assertTrue("客流" in airline or "客座率" in airline)
        for text in (daan, airport, airline):
            self.assertNotIn("DCOILWTICO", text)
            self.assertNotIn("SP500", text)

    def test_file_page_uses_local_bundle_without_fetch(self) -> None:
        from fingoose_company_impact_ui_v2 import render_workbench

        html = render_workbench(self.bundle)

        self.assertNotIn("fetch(", html)
        self.assertIn("\u5019\u9009\u95ed\u73af", html)
        self.assertIn("完整经营机制链", html)
        self.assertIn("技术详情", html)
        self.assertIn("候选闭环矩阵", html)
        self.assertIn("ui_data_bundle.js", html)
        self.assertIn("\u5b98\u65b9\u5386\u53f2\u5206\u7c7b\u5df2\u6309\u4e8b\u4ef6\u65e5\u5339\u914d", html)
        self.assertIn("\u4e8b\u4ef6\u65e5\u6709\u6548", html)
        self.assertIn("\u6765\u6e90\u5df2\u6838\u9a8c\uff0c\u89c4\u5219\u5df2\u5e94\u7528", html)
        self.assertIn("事件时间线", html)
        self.assertIn("动态传导链", html)
        self.assertIn("公司影响", html)
        self.assertIn("沪深300相对收益", html)
        self.assertIn("混杂与反证", html)

    def test_public_projection_excludes_hidden_labels(self) -> None:
        serialized = str(self.bundle)

        self.assertNotIn("benchmark_labels", serialized)
        self.assertNotIn("hidden_label_eligible", serialized)

    def test_all_timeline_nodes_have_specific_chinese_display_text(self) -> None:
        nodes = [
            node
            for event in self.bundle["events"]
            for node in event["timeline"]
        ]
        self.assertEqual(len(nodes), 50)
        self.assertEqual(len({node["fast_node_id"] for node in nodes}), 50)

        phase_labels = {
            "\u524d\u7f6e\u80cc\u666f", "\u9996\u6b21\u51b2\u51fb",
            "\u5347\u7ea7", "\u653f\u7b56\u54cd\u5e94",
            "\u7f13\u548c", "\u4e8c\u6b21\u51b2\u51fb",
        }
        for node in nodes:
            title = node["event_title_zh"]
            summary = node["event_summary_zh"]
            self.assertRegex(title, r"[\u4e00-\u9fff]")
            self.assertRegex(summary, r"[\u4e00-\u9fff]")
            self.assertNotIn("fast-event-", title)
            self.assertNotIn(title, phase_labels)
            self.assertGreaterEqual(len(title), 8)
            self.assertGreaterEqual(len(summary), 16)

    def test_event_02_titles_name_the_concrete_events(self) -> None:
        from fingoose_company_impact_ui_v2 import project_event

        event = project_event(self.bundle, "event-02")
        titles = {
            node["fast_node_id"]: node["event_title_zh"]
            for node in event["timeline"]
        }

        self.assertIn("\u7279\u522b\u519b\u4e8b\u884c\u52a8", titles["fast-event-02-M01R1"])
        self.assertIn("\u5317\u7ea6", titles["fast-event-02-M03"])
        self.assertTrue(
            any("\u4ef7\u683c\u4e0a\u9650" in title for title in titles.values())
        )
        self.assertTrue(
            all(re.search(r"[\u4e00-\u9fff]", title) for title in titles.values())
        )

    def test_timeline_renderer_prioritizes_specific_event_text(self) -> None:
        from fingoose_company_impact_ui_v2 import render_workbench

        html = render_workbench(self.bundle)

        self.assertIn("node.event_title_zh", html)
        self.assertIn("node.event_summary_zh", html)
        self.assertIn("timeline-meta", html)
        self.assertIn("timeline-tech", html)
        self.assertIn(r"\u6280\u672f\u8be6\u60c5", html)
        old_heading = (
            "${esc(zhPhase[node.phase]||node.phase||'\u9636\u6bb5\u5f85\u5b9a')} \u00b7 "
            "${esc(node.fast_node_id)}"
        )
        self.assertNotIn(old_heading, html)
    def test_complete_transmission_paths_cover_all_raw_bindings(self) -> None:
        raw_binding_ids = {
            edge["binding_id"]
            for event in self.bundle["events"]
            for edge in event["transmission_paths"]
        }
        covered_binding_ids = {
            binding_id
            for event in self.bundle["events"]
            for path in event["macro_transmission_paths"]
            for binding_id in path["binding_ids"]
        }
        unresolved_binding_ids = {
            edge["binding_id"]
            for event in self.bundle["events"]
            for edge in event["unresolved_macro_edges"]
        }

        self.assertEqual(len(raw_binding_ids), 111)
        self.assertEqual(
            raw_binding_ids, covered_binding_ids | unresolved_binding_ids
        )
        self.assertFalse(covered_binding_ids & unresolved_binding_ids)
        for event in self.bundle["events"]:
            self.assertEqual(len(event["operating_transmission_paths"]), 3)
            self.assertTrue(event["macro_transmission_paths"])
            path_keys = [
                (
                    path["channel"]["registry_id"],
                    path["market_indicator"]["registry_id"],
                )
                for path in event["macro_transmission_paths"]
            ]
            self.assertEqual(len(path_keys), len(set(path_keys)))
            for path in event["macro_transmission_paths"]:
                self.assertRegex(path["event_title_zh"], r"[\u4e00-\u9fff]")
                indicator = path["market_indicator"]
                self.assertRegex(indicator["name_zh"], r"[\u4e00-\u9fff]")
                self.assertTrue(indicator["code"])
                self.assertTrue(indicator["unit_zh"])
                self.assertTrue(indicator["economic_meaning_zh"])
                self.assertTrue(indicator["direction_interpretation_zh"])

    def test_event_01_operating_paths_are_company_specific(self) -> None:
        from fingoose_company_impact_ui_v2 import project_event

        event = project_event(self.bundle, "event-01")
        by_code = {
            path["company_code"]: path
            for path in event["operating_transmission_paths"]
        }
        daan = " ".join(node["statement"] for node in by_code["002030.SZ"]["nodes"])
        airport = " ".join(node["statement"] for node in by_code["600009.SH"]["nodes"])
        airline = " ".join(node["statement"] for node in by_code["601111.SH"]["nodes"])

        self.assertIn("\u6838\u9178\u68c0\u6d4b", daan)
        self.assertIn("\u65c5\u5ba2\u541e\u5410\u91cf", airport)
        self.assertTrue(
            "\u5ba2\u6d41" in airline or "\u5ba2\u5ea7\u7387" in airline
        )
        for path in event["operating_transmission_paths"]:
            self.assertRegex(path["nodes"][0]["statement"], r"[\u4e00-\u9fff]")
            self.assertEqual(len(path["nodes"]), 7)
            self.assertEqual(len(path["edges"]), 6)
    def test_transmission_renderer_uses_complete_path_views(self) -> None:
        from fingoose_company_impact_ui_v2 import render_workbench

        html = render_workbench(self.bundle)

        self.assertIn("transmissionMode:'operating'", html)
        self.assertIn(r"\u7ecf\u8425\u5f71\u54cd\u94fe", html)
        self.assertIn(r"\u5b8f\u89c2\u5e02\u573a\u94fe", html)
        self.assertIn("function renderOperatingPaths", html)
        self.assertIn("function renderMacroPaths", html)
        self.assertIn("path.anchor_fast_node_ids", html)
        self.assertIn("indicator.unit_zh", html)
        self.assertIn("indicator.economic_meaning_zh", html)
        self.assertIn(r"\u5e95\u5c42\u7ed1\u5b9a\u4e0e\u6280\u672f\u8be6\u60c5", html)
        self.assertNotIn(
            "function renderPaths(event){let paths=event.transmission_paths",
            html,
        )
    def test_mobile_detail_grid_allows_chart_to_shrink(self) -> None:
        from fingoose_company_impact_ui_v2 import render_workbench

        html = render_workbench(self.bundle)

        self.assertIn(
            ".detail-grid{grid-template-columns:minmax(0,1fr)}", html
        )
        self.assertIn(".detail-grid>*{min-width:0}", html)
        self.assertIn(
            ".chart-wrap{min-height:0;aspect-ratio:760/250}", html
        )
        self.assertIn(".detail-head{display:block}", html)


if __name__ == "__main__":
    unittest.main()
