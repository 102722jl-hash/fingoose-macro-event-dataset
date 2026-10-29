import json
import sys
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_ROOT.parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from src.evidence import validate_verified_node
from src.timeline import build_source_manifest, build_timeline, calculate_promotion


class TimelineBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = build_timeline(
            baseline_path=PROJECT_ROOT / "work" / "timeline_fast_candidate_v2" / "timeline_nodes.jsonl",
            audit_path=PROJECT_ROOT / "work" / "timeline_fast_candidate_v2" / "candidate_source_audit.jsonl",
            manifest_path=PROJECT_ROOT / "work" / "timeline_fast_candidate_v2" / "candidate_source_manifest.jsonl",
            workbench_events_path=PROJECT_ROOT / "work" / "ten_event_rapid_candidate_v2" / "events",
            resolutions_path=PACKAGE_ROOT / "config" / "evidence_resolutions.json",
        )

    def test_build_has_50_unique_verified_nodes_and_no_pending(self):
        nodes = self.result["nodes"]
        self.assertEqual(50, len(nodes))
        self.assertEqual(50, len({node["fast_node_id"] for node in nodes}))
        self.assertEqual({"VERIFIED_EXISTING"}, {node["evidence_status"] for node in nodes})

    def test_every_node_passes_strict_evidence_contract(self):
        failures = {
            node["fast_node_id"]: validate_verified_node(node)
            for node in self.result["nodes"]
            if validate_verified_node(node)
        }
        self.assertEqual({}, failures)

    def test_all_nodes_have_dual_time_precision_and_locators(self):
        for node in self.result["nodes"]:
            with self.subTest(node=node["fast_node_id"]):
                self.assertIn(node["occurred_at_precision"], {"DATE", "MINUTE", "SECOND"})
                self.assertIn(node["first_public_at_precision"], {"DATE", "MINUTE", "SECOND"})
                self.assertTrue(node["occurred_at_evidence"]["locator"])
                self.assertTrue(node["first_public_at_evidence"]["locator"])

    def test_event_02_m01_is_audited_semantic_replacement(self):
        node = next(node for node in self.result["nodes"] if node.get("supersedes_node_id"))
        self.assertTrue(node["semantic_change"])
        self.assertEqual("fast-event-02-M01R1", node["fast_node_id"])
        self.assertEqual("fast-event-02-M01", node["supersedes_node_id"])
        self.assertEqual("REVIEWED", node["replacement_audit"]["review_result"])
        self.assertGreater(len(node["replacement_audit"]["affected_records"]), 0)
        self.assertIn("special military operation", node["fact"])

    def test_date_only_resolutions_are_not_normalized_to_midnight(self):
        date_only_ids = {
            "fast-event-05-M04",
            "fast-event-06-M01",
            "fast-event-07-M05",
        }
        for node in self.result["nodes"]:
            if node["fast_node_id"] in date_only_ids:
                with self.subTest(node=node["fast_node_id"]):
                    self.assertEqual("DATE", node["occurred_at_precision"])
                    self.assertRegex(node["occurred_at"], r"^\d{4}-\d{2}-\d{2}$")

    def test_every_snapshot_path_resolves_from_project_root(self):
        missing = []
        for node in self.result["nodes"]:
            for source in node["evidence"]:
                snapshot_path = source.get("snapshot_path")
                if not snapshot_path or not (PROJECT_ROOT / snapshot_path).is_file():
                    missing.append((node["fast_node_id"], snapshot_path))
        self.assertEqual([], missing)
    def test_sec_acceptance_time_uses_an_independent_metadata_source(self):
        node = next(
            node for node in self.result["nodes"] if node["fast_node_id"] == "fast-event-05-M01"
        )
        self.assertEqual(
            {"sec-svb-8k-20230308", "sec-svb-8k-20230308-index"},
            set(node["source_ids"]),
        )
        self.assertEqual(
            "sec-svb-8k-20230308-index",
            node["first_public_at_evidence"]["source_id"],
        )
    def test_promotions_are_derived_from_current_nodes(self):
        promotions = self.result["promotions"]
        old_promotions = json.loads(
            (PROJECT_ROOT / "work" / "timeline_fast_candidate_v2" / "validation_report.json")
            .read_text(encoding="utf-8")
        )["promotable_count"]
        self.assertEqual(
            [node["fast_node_id"] for node in self.result["nodes"] if calculate_promotion(node)],
            [row["fast_node_id"] for row in promotions],
        )
        self.assertTrue(all(row["promotion_basis"] == "PHASE1_RECOMPUTED" for row in promotions))
        self.assertNotEqual(old_promotions, -1)


    def test_source_manifest_preserves_all_document_excerpts(self):
        manifest = {
            row["source_id"]: row
            for row in build_source_manifest(self.result["nodes"])
        }
        for source_id in ("event02-nato-statement", "event10-whitehouse-order"):
            expected = {
                (source["quote"], source["locator"])
                for node in self.result["nodes"]
                for source in node["evidence"]
                if source["source_id"] == source_id
            }
            actual = {
                (excerpt["quote"], excerpt["locator"])
                for excerpt in manifest[source_id]["evidence_excerpts"]
            }
            self.assertEqual(expected, actual)
    def test_resolution_can_preserve_multiple_exact_excerpts_from_one_document(self):
        node = next(
            row
            for row in self.result["nodes"]
            if row["fast_node_id"] == "fast-event-08-M04"
        )
        self.assertEqual(
            {"event08-boj", "event08-boj-rate"},
            set(node["source_ids"]),
        )
        self.assertEqual(2, len(node["evidence"]))
if __name__ == "__main__":
    unittest.main()
