import copy
import json
import sys
from datetime import datetime, timedelta
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from src.gates import aggregate_layer_validation, build_benchmark, validate_release_gates
from src.io_utils import read_jsonl


class BenchmarkGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.timeline = read_jsonl(PACKAGE_ROOT / "timeline_nodes.jsonl")
        cls.anchors = read_jsonl(PACKAGE_ROOT / "anchor_catalog.jsonl")
        cls.bindings = read_jsonl(PACKAGE_ROOT / "dynamic_edge_bindings.jsonl")
        cls.industries = read_jsonl(PACKAGE_ROOT / "event_industry_impacts.jsonl")
        cls.windows = read_jsonl(PACKAGE_ROOT / "company_price_windows.jsonl")
        cls.source_manifest = read_jsonl(PACKAGE_ROOT / "source_manifest.jsonl")
        cls.bundle = build_benchmark(
            timeline_nodes=cls.timeline,
            anchors=cls.anchors,
            bindings=cls.bindings,
            industry_impacts=cls.industries,
            company_windows=cls.windows,
        )

    def test_three_tracks_are_independent_without_composite_score(self):
        self.assertEqual(
            {"TIMELINE_RECONSTRUCTION", "GRAPH_CONSTRUCTION", "DIRECTION_AND_REFUSAL"},
            set(self.bundle["evaluation_report"]["tracks"]),
        )
        self.assertNotIn("composite_score", self.bundle["evaluation_report"])

    def test_examples_and_hidden_labels_are_event_isolated(self):
        self.assertEqual(10, len(self.bundle["cases"]))
        self.assertEqual(7, len(self.bundle["hidden_labels"]))
        example_ids = {
            row["event_id"] for row in self.bundle["cases"] if "example_labels" in row
        }
        hidden_ids = {row["event_id"] for row in self.bundle["hidden_labels"]}
        self.assertEqual({"event-02", "event-03", "event-04"}, example_ids)
        self.assertEqual(
            {"event-01", "event-05", "event-06", "event-07", "event-08", "event-09", "event-10"},
            hidden_ids,
        )
        self.assertTrue(example_ids.isdisjoint(hidden_ids))

    def test_public_inputs_obey_d3_cutoff_and_hide_mechanism_evidence(self):
        for case in self.bundle["cases"]:
            cutoff = case["prediction_cutoff_date"]
            with self.subTest(event=case["event_id"]):
                self.assertNotIn("timeline_nodes", case["public_input"])
                self.assertNotIn("anchor_facts", case["public_input"])
                for evidence in case["public_input"]["evidence_documents"]:
                    self.assertLessEqual(evidence["first_public_at"][:10], cutoff)
                    self.assertEqual("PUBLIC_PREDICTION", evidence["visibility"])
                    self.assertTrue(
                        {"fast_node_id", "phase", "node_action", "activation_mode"}.isdisjoint(
                            evidence
                        )
                    )
                self.assertNotIn("mechanism_evidence", case["public_input"])

    def test_human_review_graph_edges_are_not_scoring_truth(self):
        for labels in self.bundle["all_labels"]:
            for edge in labels["graph_construction"]:
                if edge["binding_status"] == "NEEDS_HUMAN_REVIEW":
                    self.assertFalse(edge["scoring_eligible"])
    def test_observation_anchors_require_refusal(self):
        for labels in self.bundle["all_labels"]:
            for decision in labels["direction_and_refusal"]:
                if decision["activation_mode"] == "OBSERVATION_ONLY":
                    self.assertTrue(decision["refusal_required"])
                    self.assertFalse(decision["causal_attribution_allowed"])

    def test_material_and_dominant_windows_are_not_clean_attribution(self):
        for labels in self.bundle["all_labels"]:
            for decision in labels["direction_and_refusal"]:
                for horizon, grade in decision["confounding_by_horizon"].items():
                    if grade in {"MATERIAL", "DOMINANT"}:
                        self.assertFalse(decision["clean_attribution_eligible_by_horizon"][horizon])

    def test_release_validator_has_no_hard_failures_but_stays_candidate(self):
        report = validate_release_gates(
            bundle=self.bundle,
            timeline_nodes=self.timeline,
            anchors=self.anchors,
            bindings=self.bindings,
            company_windows=self.windows,
            source_manifest=self.source_manifest,
            project_root=PACKAGE_ROOT.parents[1],
        )
        self.assertEqual([], report["hard_failures"])
        self.assertFalse(report["formal_ready"])
        self.assertEqual("DEFERRED", report["sha_gate"])
        self.assertFalse(
            report["checks"]["per_document_publication_time_complete"]
        )
        self.assertFalse(report["checks"]["d3_cutoff_isolation"])


    def test_public_source_ids_are_opaque(self):
        for case in self.bundle["cases"]:
            serialized = json.dumps(case["public_input"], ensure_ascii=False)
            self.assertNotIn("fast-event", serialized)
            for evidence in case["public_input"]["evidence_documents"]:
                self.assertTrue(evidence["public_source_id"].startswith("pubsrc-"))
                self.assertNotIn("source_id", evidence)

    def test_mutations_trigger_hard_failures(self):
        injected = copy.deepcopy(self.bundle)
        injected["cases"][0]["public_input"]["graph_construction"] = []
        report = validate_release_gates(
            bundle=injected,
            timeline_nodes=self.timeline,
            anchors=self.anchors,
            bindings=self.bindings,
            company_windows=self.windows,
            source_manifest=self.source_manifest,
            project_root=PACKAGE_ROOT.parents[1],
        )
        self.assertIn("PUBLIC_LABEL_LEAKAGE", report["hard_failures"])

        fabricated_timeline = copy.deepcopy(self.timeline)
        fabricated_timeline[0]["evidence"][0]["url"] = "https://fabricated.invalid/source"
        report = validate_release_gates(
            bundle=self.bundle,
            timeline_nodes=fabricated_timeline,
            anchors=self.anchors,
            bindings=self.bindings,
            company_windows=self.windows,
            source_manifest=self.source_manifest,
            project_root=PACKAGE_ROOT.parents[1],
        )
        self.assertIn("SOURCE_MANIFEST_MISMATCH", report["hard_failures"])

        bad_windows = copy.deepcopy(self.windows)
        bad_windows[0]["observations"]["T0"]["broad_market_relative_return"] = 0.25
        report = validate_release_gates(
            bundle=self.bundle,
            timeline_nodes=self.timeline,
            anchors=self.anchors,
            bindings=self.bindings,
            company_windows=bad_windows,
            source_manifest=self.source_manifest,
            project_root=PACKAGE_ROOT.parents[1],
        )
        self.assertIn("NON_RECOMPUTABLE_RELATIVE_RETURN", report["hard_failures"])
    def test_evaluation_tracks_expose_missing_scoring_truth(self):
        tracks = self.bundle["evaluation_report"]["tracks"]
        self.assertEqual("READY", tracks["TIMELINE_RECONSTRUCTION"]["status"])
        self.assertEqual(
            "BLOCKED_NO_SCORING_LABELS",
            tracks["GRAPH_CONSTRUCTION"]["status"],
        )
        self.assertEqual(
            "BLOCKED_NO_SCORING_LABELS",
            tracks["DIRECTION_AND_REFUSAL"]["status"],
        )

    def test_vocabulary_smuggling_and_source_metadata_mutations_fail(self):
        smuggled = copy.deepcopy(self.bundle)
        smuggled["cases"][0]["public_input"]["allowed_channel_vocabulary"] = [
            json.dumps(smuggled["all_labels"][0]["graph_construction"])
        ]
        report = validate_release_gates(
            bundle=smuggled,
            timeline_nodes=self.timeline,
            anchors=self.anchors,
            bindings=self.bindings,
            company_windows=self.windows,
            source_manifest=self.source_manifest,
            project_root=PACKAGE_ROOT.parents[1],
        )
        self.assertIn("PUBLIC_VOCABULARY_INVALID", report["hard_failures"])

        for field, value in (
            ("quote", "fabricated quote"),
            ("locator", "fabricated locator"),
            ("publisher", "fabricated publisher"),
            ("source_tier", "D"),
        ):
            with self.subTest(field=field):
                mutated = copy.deepcopy(self.timeline)
                mutated[0]["evidence"][0][field] = value
                report = validate_release_gates(
                    bundle=self.bundle,
                    timeline_nodes=mutated,
                    anchors=self.anchors,
                    bindings=self.bindings,
                    company_windows=self.windows,
                    source_manifest=self.source_manifest,
                    project_root=PACKAGE_ROOT.parents[1],
                )
                self.assertIn("SOURCE_MANIFEST_MISMATCH", report["hard_failures"])

    def test_d3_gate_compares_exact_publication_instants(self):
        mutated = copy.deepcopy(self.bundle)
        cutoff = datetime.fromisoformat(
            mutated["cases"][0]["prediction_cutoff_at"].replace("Z", "+00:00")
        )
        leaked = mutated["cases"][0]["public_input"]["evidence_documents"][0]
        leaked["first_public_at"] = (cutoff + timedelta(seconds=1)).isoformat()
        leaked["first_public_at_precision"] = "SECOND"
        report = validate_release_gates(
            bundle=mutated,
            timeline_nodes=self.timeline,
            anchors=self.anchors,
            bindings=self.bindings,
            company_windows=self.windows,
            source_manifest=self.source_manifest,
            project_root=PACKAGE_ROOT.parents[1],
        )
        self.assertIn("D3_LEAKAGE", report["hard_failures"])

    def test_public_evidence_documents_are_bound_to_trusted_timeline(self):
        for field, value in (
            ("quote", "fabricated public quote"),
            ("url", "https://fabricated.invalid/public-source"),
            ("publisher", "Fabricated Publisher"),
            ("public_source_id", "pubsrc-fabricated"),
            ("first_public_at", "1999-01-01T00:00:00Z"),
        ):
            with self.subTest(field=field):
                mutated = copy.deepcopy(self.bundle)
                mutated["cases"][0]["public_input"]["evidence_documents"][0][field] = value
                report = validate_release_gates(
                    bundle=mutated,
                    timeline_nodes=self.timeline,
                    anchors=self.anchors,
                    bindings=self.bindings,
                    company_windows=self.windows,
                    source_manifest=self.source_manifest,
                    project_root=PACKAGE_ROOT.parents[1],
                )
                self.assertIn("PUBLIC_EVIDENCE_MISMATCH", report["hard_failures"])

    def test_pdf_quotes_are_checked_and_hash_gaps_keep_authenticity_partial(self):
        report = validate_release_gates(
            bundle=self.bundle,
            timeline_nodes=self.timeline,
            anchors=self.anchors,
            bindings=self.bindings,
            company_windows=self.windows,
            source_manifest=self.source_manifest,
            project_root=PACKAGE_ROOT.parents[1],
        )
        self.assertEqual(4, report["source_validation"]["pdf_quote_snapshot_checked_count"])
        self.assertEqual(0, report["source_validation"]["binary_quote_snapshot_unchecked_count"])
        self.assertFalse(report["checks"]["source_authenticity"])

    def test_top_level_validation_aggregates_layer_failures(self):
        combined = aggregate_layer_validation(
            {"hard_failures": [], "checks": {}},
            ["BINDING_LAYER_FAILURE"],
            ["MARKET_LAYER_FAILURE"],
        )
        self.assertEqual(
            ["BINDING_LAYER_FAILURE", "MARKET_LAYER_FAILURE"],
            combined["hard_failures"],
        )
        self.assertFalse(combined["checks"]["binding_layer_gate"])
        self.assertFalse(combined["checks"]["market_layer_gate"])
if __name__ == "__main__":
    unittest.main()
