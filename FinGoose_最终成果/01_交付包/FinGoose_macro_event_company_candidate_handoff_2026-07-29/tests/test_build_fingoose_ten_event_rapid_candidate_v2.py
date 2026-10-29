from __future__ import annotations

import sys
import json
from copy import deepcopy
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


class TenEventRapidConfigTests(unittest.TestCase):
    def test_registry_covers_ten_events_four_assets_and_35_paths(self) -> None:
        from fingoose_ten_event_rapid_config import CORE_PATH_SPECS, EVENT_CONFIGS

        self.assertEqual(
            set(EVENT_CONFIGS),
            {f"event-{index:02d}" for index in range(1, 11)},
        )
        self.assertTrue(
            all(len(row["core_series_ids"]) == 4 for row in EVENT_CONFIGS.values())
        )
        counts = {
            event_id: sum(path["event_id"] == event_id for path in CORE_PATH_SPECS)
            for event_id in EVENT_CONFIGS
        }
        self.assertTrue(all(3 <= count <= 4 for count in counts.values()))
        self.assertEqual(len(CORE_PATH_SPECS), 35)
        self.assertEqual(len({row["path_id"] for row in CORE_PATH_SPECS}), 35)


class TenEventStorylineTests(unittest.TestCase):
    def test_storyline_specs_cover_ten_events_with_real_titles(self) -> None:
        from fingoose_event_storylines import STORYLINE_SPECS

        self.assertEqual(
            set(STORYLINE_SPECS),
            {f"event-{index:02d}" for index in range(1, 11)},
        )
        referenced_nodes = []
        for event_id, rows in STORYLINE_SPECS.items():
            self.assertTrue(5 <= len(rows) <= 9, event_id)
            self.assertEqual(len({row["story_step_id"] for row in rows}), len(rows))
            for row in rows:
                self.assertTrue(row["title_cn"].strip(), row["story_step_id"])
                self.assertNotIn("事件节点", row["title_cn"])
                for field in ("narrative_cn", "before_state_cn", "after_state_cn", "significance_cn"):
                    self.assertTrue(row[field].strip(), f"{row['story_step_id']}:{field}")
                referenced_nodes.extend(row["evidence_node_ids"])
        self.assertEqual(len(referenced_nodes), 50)
        self.assertEqual(len(set(referenced_nodes)), 50)
        self.assertEqual(STORYLINE_SPECS["event-01"][-1]["phase"], "RESOLUTION")

    def test_build_storylines_derives_status_and_references(self) -> None:
        from build_fingoose_ten_event_rapid_candidate_v2 import (
            build_core_paths,
            build_market_packages,
            build_source_registry,
            build_storylines,
            build_timelines,
        )

        timelines = build_timelines(ROOT)
        paths = build_core_paths(ROOT, build_source_registry(ROOT))
        markets = build_market_packages(ROOT)
        rows = build_storylines(timelines, paths, markets)
        self.assertEqual(sum(len(row["steps"]) for row in rows.values()), 50)
        self.assertEqual(
            sum(
                step["evidence_status"] == "PENDING_EVIDENCE"
                for row in rows.values()
                for step in row["steps"]
            ),
            8,
        )
        ending = rows["event-01"]["steps"][-1]
        self.assertEqual(ending["phase"], "RESOLUTION")
        self.assertEqual(ending["evidence_status"], "SUPPORTED")
        china_anchor = rows["event-04"]["steps"][2]
        self.assertEqual(china_anchor["evidence_status"], "PARTIALLY_SUPPORTED")
        self.assertEqual(china_anchor["time_precision"], "DATE")

    def test_storyline_validation_rejects_unknown_references(self) -> None:
        from build_fingoose_ten_event_rapid_candidate_v2 import _validate_storyline

        failures = _validate_storyline(
            "event-01",
            {
                "event_id": "event-01",
                "steps": [{
                    "story_step_id": "broken",
                    "sequence": 1,
                    "evidence_node_ids": ["missing-node"],
                    "activated_path_ids": ["missing-path"],
                    "amplified_path_ids": [],
                    "weakened_path_ids": [],
                    "market_series_ids": ["missing-series"],
                    "evidence_status": "SUPPORTED",
                    "title_cn": "损坏引用",
                    "narrative_cn": "用于验证未知引用。",
                    "before_state_cn": "验证前。",
                    "after_state_cn": "验证后。",
                    "significance_cn": "验证引用解析。",
                }],
            },
            {"event_id": "event-01", "nodes": []},
            [],
            [],
        )
        self.assertTrue(any("UNKNOWN_EVIDENCE_NODE" in row for row in failures))
        self.assertTrue(any("UNKNOWN_PATH" in row for row in failures))
        self.assertTrue(any("UNKNOWN_MARKET_SERIES" in row for row in failures))

class TenEventAssemblerTests(unittest.TestCase):
    def test_every_path_declares_semantic_activation_rules(self) -> None:
        from fingoose_ten_event_rapid_config import CORE_PATH_SPECS

        for path in CORE_PATH_SPECS:
            self.assertTrue(path["activation_phases"], path["path_id"])
            self.assertTrue(path["activation_actions"], path["path_id"])
            self.assertTrue(path["activation_tags"], path["path_id"])



    def test_timelines_keep_50_nodes_and_real_pending_boundaries(self) -> None:
        from build_fingoose_ten_event_rapid_candidate_v2 import build_timelines

        rows = build_timelines(ROOT)
        self.assertEqual(sum(len(row["nodes"]) for row in rows.values()), 50)
        self.assertEqual(
            sum(
                node["evidence_status"] == "PENDING_EVIDENCE"
                for event in rows.values()
                for node in event["nodes"]
            ),
            8,
        )
        self.assertTrue(
            all(
                sum(node["anchor_role"] == "PRIMARY" for node in event["nodes"]) == 1
                for event in rows.values()
            )
        )

    def test_core_paths_resolve_fact_and_mechanism_sources(self) -> None:
        from build_fingoose_ten_event_rapid_candidate_v2 import (
            build_core_paths,
            build_source_registry,
        )

        sources = build_source_registry(ROOT)
        paths = build_core_paths(ROOT, sources)
        self.assertEqual(sum(len(rows) for rows in paths.values()), 35)
        for rows in paths.values():
            for path in rows:
                self.assertEqual(path["confirmation_status"], "PROPOSED")
                if path["scoring_eligible"]:
                    self.assertTrue(path["event_fact_evidence"])
                self.assertTrue(path["mechanism_evidence"])
                self.assertTrue(
                    all(source_id in sources for source_id in path["event_fact_evidence"])
                )
                self.assertTrue(
                    all(ref["source_id"] in sources for ref in path["mechanism_evidence"])
                )

    def test_stage_specific_paths_use_semantic_anchors(self) -> None:
        from build_fingoose_ten_event_rapid_candidate_v2 import (
            build_core_paths,
            build_source_registry,
        )

        paths = build_core_paths(ROOT, build_source_registry(ROOT))
        by_id = {
            path["path_id"]: path
            for event_paths in paths.values()
            for path in event_paths
        }
        self.assertEqual(
            by_id["event-07-P-shipping-disruption"]["anchor_fast_node_ids"],
            ["fast-event-07-M04"],
        )
        self.assertEqual(
            by_id["event-02-P-sanctions-trade"]["anchor_fast_node_ids"],
            ["fast-event-02-M05"],
        )
        self.assertEqual(
            by_id["event-07-P-risk-appetite"]["anchor_fast_node_ids"],
            ["fast-event-07-M01"],
        )

    def test_unmatched_semantic_path_does_not_fall_back_to_primary(self) -> None:
        from build_fingoose_ten_event_rapid_candidate_v2 import (
            _select_path_anchor,
            build_timelines,
        )

        nodes = build_timelines(ROOT)["event-01"]["nodes"]
        spec = {
            "activation_phases": ["POLICY_RESPONSE"],
            "activation_actions": ["WEAKENS"],
            "activation_tags": ["NON_EXISTENT_TAG"],
        }
        anchor, pending = _select_path_anchor(spec, nodes)
        self.assertIsNone(anchor)
        self.assertIsNone(pending)


    def test_curated_sequence_exposes_timestamp_inversions(self) -> None:
        from build_fingoose_ten_event_rapid_candidate_v2 import build_timelines

        timelines = build_timelines(ROOT)
        warned = {
            event_id
            for event_id, timeline in timelines.items()
            if timeline["chronology_warnings"]
        }
        self.assertEqual(warned, {"event-01", "event-09", "event-10"})
        for event_id in warned:
            self.assertEqual(
                timelines[event_id]["chronology_status"],
                "CURATED_SEQUENCE_WITH_TIMESTAMP_INVERSIONS",
            )
            self.assertEqual(timelines[event_id]["ordering_basis"], "CURATED_SEQUENCE")


class TenEventMarketTests(unittest.TestCase):
    def test_market_packages_have_four_core_series_and_six_display_windows(self) -> None:
        from build_fingoose_ten_event_rapid_candidate_v2 import build_market_packages

        packages = build_market_packages(ROOT)
        self.assertEqual(
            set(packages),
            {f"event-{index:02d}" for index in range(1, 11)},
        )
        for rows in packages.values():
            self.assertEqual(
                len([row for row in rows if row["asset_tier"] == "CORE"]),
                4,
            )
            for row in rows:
                self.assertEqual(list(row["display_windows"]), [
                    "T-1", "T0", "D1", "D3", "D5", "D20",
                ])
                self.assertIsNotNone(row["display_windows"]["T-1"]["value"])
                self.assertTrue(row["formulas"]["raw_change"])
                self.assertEqual(row["daily_t0_rule"], "T0_CLOSE_EQUALS_D1")

class TenEventHardFailureTests(unittest.TestCase):
    def _valid_inputs(self, event_id: str):
        from build_fingoose_ten_event_rapid_candidate_v2 import (
            build_confounders,
            build_core_paths,
            build_market_packages,
            build_source_registry,
            build_timelines,
        )

        sources = build_source_registry(ROOT)
        return (
            build_timelines(ROOT)[event_id],
            build_core_paths(ROOT, sources)[event_id],
            build_market_packages(ROOT)[event_id],
            build_confounders()[event_id],
            sources,
        )

    def test_rejects_cross_event_fact_source(self) -> None:
        from build_fingoose_ten_event_rapid_candidate_v2 import _validate_event

        timeline, paths, windows, confounders, sources = self._valid_inputs("event-01")
        timeline = deepcopy(timeline)
        foreign_source = next(
            source_id
            for source_id, source in sources.items()
            if source.get("event_id") == "event-10"
        )
        timeline["nodes"][0]["source_ids"] = [foreign_source]
        failures = _validate_event(
            "event-01", timeline, paths, windows, sources, confounders
        )
        self.assertTrue(any("CROSS_EVENT_SOURCE" in item for item in failures))

    def test_rejects_pending_node_promotion_and_links(self) -> None:
        from build_fingoose_ten_event_rapid_candidate_v2 import _validate_event

        timeline, paths, windows, confounders, sources = self._valid_inputs("event-02")
        timeline = deepcopy(timeline)
        pending = next(
            node
            for node in timeline["nodes"]
            if node["evidence_status"] == "PENDING_EVIDENCE"
        )
        pending["promotion_eligible"] = True
        pending["linked_path_ids"] = [paths[0]["path_id"]]
        failures = _validate_event(
            "event-02", timeline, paths, windows, sources, confounders
        )
        self.assertTrue(any("PENDING_PROMOTION_ELIGIBLE" in item for item in failures))
        self.assertTrue(any("PENDING_WITH_LINKED_PATHS" in item for item in failures))

    def test_rejects_scored_path_without_evidence_or_review_contract(self) -> None:
        from build_fingoose_ten_event_rapid_candidate_v2 import _validate_event

        timeline, paths, windows, confounders, sources = self._valid_inputs("event-03")
        paths = deepcopy(paths)
        path = paths[0]
        path["event_fact_evidence"] = []
        path["mechanism_evidence"] = []
        path["selection_status"] = "CONFIRMED"
        path["review_basis"] = "HUMAN_CONFIRMED"
        failures = _validate_event(
            "event-03", timeline, paths, windows, sources, confounders
        )
        self.assertTrue(any("SELECTION_STATUS" in item for item in failures))
        self.assertTrue(any("REVIEW_BASIS" in item for item in failures))
        self.assertTrue(any("SCORING_WITHOUT_FACT_EVIDENCE" in item for item in failures))
        self.assertTrue(any("SCORING_WITHOUT_MECHANISM_EVIDENCE" in item for item in failures))


    def test_rejects_hidden_mechanism_marked_available_at_anchor(self) -> None:
        from build_fingoose_ten_event_rapid_candidate_v2 import _validate_event

        timeline, paths, windows, confounders, sources = self._valid_inputs("event-02")
        paths = deepcopy(paths)
        hidden_ref = next(
            ref
            for path in paths
            for ref in path["mechanism_evidence"]
            if sources[ref["source_id"]]["visibility"]
            == "HIDDEN_FROM_PRIMARY_PREDICTION"
        )
        hidden_ref["prediction_use"] = "AVAILABLE_AT_ANCHOR"
        failures = _validate_event(
            "event-02", timeline, paths, windows, sources, confounders
        )
        self.assertTrue(any("MECHANISM_VISIBILITY" in item for item in failures))

    def test_rejects_invalid_core_assets_and_daily_alias_contract(self) -> None:
        from build_fingoose_ten_event_rapid_candidate_v2 import _validate_event

        timeline, paths, windows, confounders, sources = self._valid_inputs("event-03")
        windows = deepcopy(windows)
        windows[1]["series_id"] = windows[0]["series_id"]
        row = windows[0]
        row["display_windows"]["T0"]["value"] += 1
        row["formulas"]["raw_change"] = ""
        row["timezone"] = None
        row["calendar_id"] = None
        failures = _validate_event(
            "event-03", timeline, paths, windows, sources, confounders
        )
        for token in (
            "DUPLICATE_SERIES",
            "CORE_ASSET_SET",
            "T0_D1_MISMATCH",
            "MISSING_FORMULA",
            "MISSING_TIMEZONE",
            "MISSING_CALENDAR",
        ):
            self.assertTrue(any(token in item for item in failures), token)

    def test_rejects_unresolved_confounder_horizon_without_item_coverage(self) -> None:
        from build_fingoose_ten_event_rapid_candidate_v2 import _validate_event

        timeline, paths, windows, confounders, sources = self._valid_inputs("event-04")
        confounders = deepcopy(confounders)
        confounders["by_horizon"]["T0"] = "UNRESOLVED"
        self.assertTrue(all(
            "T0" not in item["affected_windows"]
            for item in confounders["items"]
        ))
        failures = _validate_event(
            "event-04", timeline, paths, windows, sources, confounders
        )
        self.assertTrue(any("CONFOUNDER_WINDOW_UNSUPPORTED:T0" in item for item in failures))


class TenEventConfounderTests(unittest.TestCase):
    def test_material_confounders_route_long_windows_out_of_clean_scoring(self) -> None:
        from build_fingoose_ten_event_rapid_candidate_v2 import (
            build_confounders,
            build_stage_mappings,
            build_timelines,
        )

        confounders = build_confounders()
        mappings = build_stage_mappings(build_timelines(ROOT))
        self.assertEqual(
            set(confounders),
            {f"event-{index:02d}" for index in range(1, 11)},
        )
        self.assertTrue(
            all(
                row["clean_attribution_decision"]
                in {"CHALLENGE_ONLY", "WINDOW_DEPENDENT", "UNRESOLVED"}
                for row in confounders.values()
            )
        )
        self.assertTrue(
            all(
                len(mappings[event_id]["node_mappings"]) == 5
                for event_id in mappings
            )
        )
        self.assertTrue(
            any(
                level == "DOMINANT"
                for row in confounders.values()
                for level in row["by_horizon"].values()
            )
        )

class TenEventOutputTests(unittest.TestCase):
    def _build_overview_html(self) -> str:
        import tempfile

        from build_fingoose_ten_event_rapid_candidate_v2 import build

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "ten_event_rapid_candidate_v2"
            build(ROOT, output)
            return (output / "index.html").read_text(encoding="utf-8")

    def test_workbench_renders_storyline_before_evidence_timeline(self) -> None:
        page = self._build_overview_html()
        self.assertEqual(page.count("class='story-step"), 50)
        self.assertIn("01 · 事件发展时间线", page)
        self.assertIn("02 · 证据时间线", page)
        self.assertLess(page.index("01 · 事件发展时间线"), page.index("02 · 证据时间线"))
        for token in (
            "story-drawer", "selectStoryStep(",
            "data-story-step-id=", "data-evidence-node-ids=",
        ):
            self.assertIn(token, page)
        self.assertIn("WHO 结束 PHEIC，事件进入常态化管理", page)

    def test_workbench_story_selection_contract_is_bidirectional(self) -> None:
        page = self._build_overview_html()
        for token in (
            "function selectStoryStep(stepId)",
            "function storyStepsForNode(view,nodeId)",
            "story.dataset.evidenceNodeIds",
            "story.dataset.pathIds",
            "story.dataset.seriesIds",
            'view.querySelectorAll(".market-card")',
            ".story-step.selected",
            ".market-card.selected",
            ".market-card{padding:16px;min-width:0",
        ):
            self.assertIn(token, page)
    def test_overview_is_linked_research_workbench(self) -> None:
        page = self._build_overview_html()
        self.assertIn('class="event-sidebar"', page)
        self.assertIn('data-event-id="event-02"', page)
        self.assertIn('id="research-main"', page)
        self.assertIn('data-node-id=', page)
        self.assertEqual(page.count("<button class='timeline-node"), 50)
        self.assertIn("<svg", page)
        self.assertIn("混杂与竞争解释", page)
        visible = page.split('<script id="workbench-data"', 1)[0]
        self.assertNotIn("RAPID_CANDIDATE", visible)
        self.assertNotIn("PENDING_EVIDENCE", visible)

    def test_workbench_contains_cross_section_linkage_contract(self) -> None:
        page = self._build_overview_html()
        for token in (
            "selectEvent(",
            "selectTimelineNode(",
            "data-path-id=",
            "scrollIntoView",
            "windowPoints",
        ):
            self.assertIn(token, page)

    def test_ui_copy_maps_status_phase_and_market_labels_to_chinese(self) -> None:
        from build_fingoose_ten_event_rapid_candidate_v2 import ui_copy

        copy = ui_copy()
        self.assertEqual(copy["status"]["PENDING_EVIDENCE"], "待补证")
        self.assertEqual(copy["phase"]["INITIAL_SHOCK"], "首次冲击")
        self.assertEqual(copy["window"]["T-1"], "前一交易日")

    def test_build_emits_ten_event_pages_and_overview(self) -> None:
        import tempfile

        from build_fingoose_ten_event_rapid_candidate_v2 import build

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "ten_event_rapid_candidate_v2"
            report = build(ROOT, output)
            self.assertEqual(report["event_count"], 10)
            self.assertEqual(report["hard_failures"], [])
            self.assertEqual(report["chronology_warning_count"], 3)
            self.assertEqual(len(report["chronology_warnings"]), 3)
            self.assertTrue((output / "index.html").exists())
            overview = (output / "index.html").read_text(encoding="utf-8")
            for token in (
                "待补证", "扩展资产", "验证状态",
                f"<b>{report['pending_evidence_count']}</b> 待补证节点",
            ):
                self.assertIn(token, overview)
            for index in range(1, 11):
                event_root = output / "events" / f"event-{index:02d}"
                self.assertTrue((event_root / "index.html").exists())
                event_report = json.loads(
                    (event_root / "validation_report.json").read_text(encoding="utf-8")
                )
                self.assertIn("chronology_status", event_report)
                self.assertIn("chronology_warnings", event_report)
                page = (event_root / "index.html").read_text(encoding="utf-8")
                for token in (
                    "事实来源", "事件事实依据", "机制依据", "绝对值与变化",
                    'target="_blank"', 'rel="noopener noreferrer"',
                    "chronology-note", "叙事顺序",
                ):
                    self.assertIn(token, page)

class TenEventRepeatabilityTests(unittest.TestCase):
    def test_core_path_build_does_not_mutate_global_config(self) -> None:
        from build_fingoose_ten_event_rapid_candidate_v2 import (
            build_core_paths,
            build_source_registry,
        )

        sources = build_source_registry(ROOT)
        first = build_core_paths(ROOT, sources)
        second = build_core_paths(ROOT, sources)
        self.assertEqual(first, second)

    def test_output_tree_validation_rejects_stale_event_content(self) -> None:
        import tempfile

        from build_fingoose_ten_event_rapid_candidate_v2 import (
            _validate_output_tree,
            build,
        )

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "ten_event_rapid_candidate_v2"
            build(ROOT, output)
            stale_dir = output / "events" / "event-99"
            stale_dir.mkdir()
            (stale_dir / "index.html").write_text("stale", encoding="utf-8")
            stale_file = output / "events" / "event-01" / "stale.json"
            stale_file.write_text("{}", encoding="utf-8")
            failures = _validate_output_tree(output)
            self.assertTrue(any("UNEXPECTED_EVENT_DIR:event-99" in row for row in failures))
            self.assertTrue(any("UNEXPECTED_EVENT_FILE:event-01:stale.json" in row for row in failures))


class TenEventRenderedScriptTests(unittest.TestCase):
    def test_generated_page_contains_valid_quote_escape_mapping(self) -> None:
        import tempfile

        from build_fingoose_ten_event_rapid_candidate_v2 import build

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "ten_event_rapid_candidate_v2"
            build(ROOT, output)
            page = (
                output / "events" / "event-02" / "index.html"
            ).read_text(encoding="utf-8")
            self.assertIn("'\"':\"&quot;\"", page)
            self.assertNotIn('""":"&quot;"', page)
            self.assertIn(
                '<script id="workbench-data" type="application/json">',
                page,
            )
            self.assertIn('<link rel="icon" href="data:,">', page)

