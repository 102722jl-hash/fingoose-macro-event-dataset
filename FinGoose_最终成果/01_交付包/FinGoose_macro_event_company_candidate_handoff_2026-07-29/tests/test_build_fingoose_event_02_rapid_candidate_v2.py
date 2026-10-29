from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class Event02RapidCandidateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.output = Path(self.tmp.name) / "event_02_rapid_candidate_v2"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def build(self) -> None:
        from build_fingoose_event_02_rapid_candidate_v2 import build

        build(ROOT, self.output)

    def test_build_preserves_timeline_evidence_boundaries(self) -> None:
        self.build()
        timeline = json.loads((self.output / "timeline.json").read_text(encoding="utf-8"))

        self.assertEqual(timeline["event_id"], "event-02")
        self.assertEqual(len(timeline["nodes"]), 5)
        self.assertEqual(
            [row["fast_node_id"] for row in timeline["nodes"]],
            [f"fast-event-02-M0{index}" for index in range(1, 6)],
        )
        m01 = timeline["nodes"][0]
        self.assertEqual(m01["evidence_status"], "PENDING_EVIDENCE")
        self.assertIsNone(m01["occurred_at"])
        self.assertFalse(m01["promotion_eligible"])
        self.assertEqual(timeline["daily_resolution"]["status"], "SAME_DAY_UNRESOLVED")
        self.assertEqual(
            set(timeline["daily_resolution"]["node_ids"]),
            {"fast-event-02-M03", "fast-event-02-M04"},
        )

    def test_four_core_paths_remain_proposals_with_separate_evidence_scopes(self) -> None:
        self.build()
        payload = json.loads(
            (self.output / "core_transmission_paths.json").read_text(encoding="utf-8")
        )

        self.assertEqual(len(payload["paths"]), 4)
        for path in payload["paths"]:
            self.assertEqual(path["selection_status"], "CORE_REVIEWED")
            self.assertEqual(path["confirmation_status"], "PROPOSED")
            self.assertTrue(path["event_fact_evidence"])
            self.assertTrue(path["mechanism_evidence"])
            self.assertTrue(path["conditions"])
            self.assertTrue(path["invalidation_conditions"])
            self.assertEqual(
                set(path["expected_direction"]),
                {"IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM"},
            )
            self.assertTrue(all(
                item["evidence_scope"] != "EVENT_FACT_AND_TIME"
                for item in path["mechanism_evidence"]
            ))

    def test_market_rows_show_absolute_values_and_reproducible_changes(self) -> None:
        self.build()
        rows = read_jsonl(self.output / "market_windows.jsonl")

        self.assertEqual(
            {row["series_id"] for row in rows},
            {"DCOILBRENTEU", "DHHNGSP", "DGS10", "VIXCLS", "SP500"},
        )
        for row in rows:
            self.assertEqual(
                list(row["display_windows"]),
                ["T-1", "T0", "D1", "D3", "D5", "D20"],
            )
            baseline = row["display_windows"]["T-1"]
            self.assertIsNotNone(baseline["date"])
            self.assertIsNotNone(baseline["value"])
            self.assertEqual(baseline["raw_change"], 0.0)
            self.assertEqual(
                row["display_windows"]["T0"]["date"],
                row["display_windows"]["D1"]["date"],
            )
            self.assertEqual(
                row["display_windows"]["T0"]["value"],
                row["display_windows"]["D1"]["value"],
            )
            self.assertEqual(row["daily_t0_rule"], "T0_CLOSE_EQUALS_D1")
            self.assertTrue(row["formulas"]["raw_change"])
            self.assertTrue(row["formulas"]["standardized_change"])
            self.assertIn("relative_change", row["formulas"])

            for label, point in row["display_windows"].items():
                if point is None:
                    continue
                self.assertIn("date", point, label)
                self.assertIn("value", point, label)
                self.assertIn("raw_change", point, label)
                self.assertIn("standardized_change", point, label)
                self.assertIn("relative_change", point, label)
                self.assertIn("empirical_percentile", point, label)

    def test_stage_mapping_and_confounders_prevent_clean_overclaim(self) -> None:
        self.build()
        mapping = json.loads(
            (self.output / "stage_edge_market_map.json").read_text(encoding="utf-8")
        )
        confounders = json.loads(
            (self.output / "confounders.json").read_text(encoding="utf-8")
        )

        self.assertEqual(len(mapping["node_mappings"]), 5)
        self.assertEqual(mapping["node_mappings"][0]["market_window_status"], "NOT_COMPUTED")
        m05 = next(row for row in mapping["node_mappings"] if row["fast_node_id"].endswith("M05"))
        self.assertEqual(m05["market_window_status"], "OUTSIDE_PRIMARY_ANCHOR_WINDOW")
        self.assertEqual(confounders["clean_attribution_decision"], "CHALLENGE_ONLY")
        self.assertEqual(confounders["by_horizon"]["D20"], "DOMINANT")
        self.assertTrue(confounders["items"])

    def test_validation_report_and_readonly_page_are_complete(self) -> None:
        self.build()
        report = json.loads(
            (self.output / "validation_report.json").read_text(encoding="utf-8")
        )
        page = (self.output / "index.html").read_text(encoding="utf-8")

        self.assertEqual(report["release_tier"], "RAPID_CANDIDATE")
        self.assertFalse(report["formal_ready"])
        self.assertFalse(report["production_dataset_modified"])
        self.assertEqual(report["hard_failures"], [])
        self.assertIn("event-02-M01", " ".join(report["warnings"]))
        for token in (
            "事件时间线", "动态传导链", "绝对值与变化", "混杂与竞争解释",
            "SAME_DAY_UNRESOLVED", "T0_CLOSE_EQUALS_D1",
        ):
            self.assertIn(token, page)


    def test_timeline_and_paths_render_resolvable_inline_citations(self) -> None:
        self.build()
        timeline = json.loads((self.output / "timeline.json").read_text(encoding="utf-8"))
        paths = json.loads(
            (self.output / "core_transmission_paths.json").read_text(encoding="utf-8")
        )["paths"]
        sources = {
            row["source_id"]: row
            for row in json.loads((self.output / "sources.json").read_text(encoding="utf-8"))
        }
        page = (self.output / "index.html").read_text(encoding="utf-8")

        for node in timeline["nodes"]:
            if node["evidence_status"] == "VERIFIED_EXISTING":
                self.assertTrue(node["source_ids"])
                self.assertTrue(
                    all(sources[source_id]["url"] for source_id in node["source_ids"])
                )
        self.assertEqual(timeline["nodes"][0]["source_ids"], [])
        for path in paths:
            ids = path["event_fact_evidence"] + [
                row["source_id"] for row in path["mechanism_evidence"]
            ]
            self.assertTrue(all(sources[source_id]["url"] for source_id in ids))
        for token in (
            "citationLinks", "\u4e8b\u5b9e\u6765\u6e90", "\u4e8b\u4ef6\u4e8b\u5b9e\u4f9d\u636e", "\u673a\u5236\u4f9d\u636e",
            "\u4e8b\u540e\u673a\u5236\u9a8c\u8bc1", "\u6682\u65e0\u5df2\u9a8c\u8bc1\u5f15\u7528", 'target="_blank"',
            'rel="noopener noreferrer"',
        ):
            self.assertIn(token, page)
        self.assertEqual(
            page.count("document.getElementById('timeline-list').innerHTML"),
            1,
        )
        self.assertEqual(page.count("document.getElementById('path-list').innerHTML"), 1)
        self.assertIn('<a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">', page)


if __name__ == "__main__":
    unittest.main()
