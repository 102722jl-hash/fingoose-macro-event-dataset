import copy
import json
import sys
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_ROOT.parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from src.bindings import _load_mechanism_sources, binding_hard_failures, review_bindings
from src.io_utils import read_jsonl


class BindingReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.timeline = read_jsonl(PACKAGE_ROOT / "timeline_nodes.jsonl")
        cls.anchors = read_jsonl(
            PROJECT_ROOT / "work" / "transmission_24_anchor_v2_candidate" / "anchor_catalog.jsonl"
        )
        cls.bindings = read_jsonl(
            PROJECT_ROOT
            / "work"
            / "transmission_24_anchor_v2_candidate"
            / "dynamic_edge_bindings.jsonl"
        )
        cls.result = review_bindings(
            timeline_nodes=cls.timeline,
            anchors=cls.anchors,
            bindings=cls.bindings,
            workbench_events_path=PROJECT_ROOT / "work" / "ten_event_rapid_candidate_v2" / "events",
            reviewed_at="2026-08-01T12:00:00+08:00",
        )

    def test_all_24_anchors_and_111_bindings_are_preserved(self):
        self.assertEqual(24, len(self.result["anchors"]))
        self.assertEqual(111, len(self.result["bindings"]))
        self.assertEqual(111, len({row["binding_id"] for row in self.result["bindings"]}))

    def test_final_bindings_have_only_allowed_review_states(self):
        allowed = {"AI_REVIEWED", "REJECTED", "NEEDS_HUMAN_REVIEW"}
        states = {row["binding_status"] for row in self.result["bindings"]}
        self.assertTrue(states <= allowed)
        self.assertNotIn("PROPOSED", states)
        self.assertNotIn("CONFIRMED", states)

    def test_each_binding_has_directions_lag_conditions_and_review(self):
        for row in self.result["bindings"]:
            with self.subTest(binding=row["binding_id"]):
                self.assertEqual(
                    {"IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM"}, set(row["expected_path"])
                )
                self.assertTrue(row["lag"]["minimum"])
                self.assertTrue(row["lag"]["maximum"])
                self.assertTrue(row["conditions"])
                self.assertTrue(row["invalidation_conditions"])
                self.assertEqual("AI_DESK_REVIEW", row["review"]["reviewer_type"])
                self.assertTrue(row["review"]["rationale_zh"])

    def test_event_fact_and_mechanism_evidence_are_separate(self):
        for row in self.result["bindings"]:
            with self.subTest(binding=row["binding_id"]):
                fact_ids = {item["evidence_id"] for item in row["event_fact_evidence"]}
                mechanism_ids = {item["evidence_id"] for item in row["mechanism_evidence"]}
                self.assertTrue(fact_ids)
                self.assertTrue(mechanism_ids)
                self.assertTrue(fact_ids.isdisjoint(mechanism_ids))
                self.assertTrue(
                    all(
                        item["visibility"] == "HIDDEN_FROM_PRIMARY_PREDICTION"
                        for item in row["mechanism_evidence"]
                    )
                )

    def test_all_39_unlinked_counterevidence_items_are_disposed(self):
        self.assertEqual(39, len(self.result["counterevidence_dispositions"]))
        self.assertEqual(
            {"NOT_APPLICABLE"},
            {row["disposition"] for row in self.result["counterevidence_dispositions"]},
        )
        self.assertNotIn(
            "UNLINKED", {row["counterevidence_status"] for row in self.result["bindings"]}
        )

    def test_observation_anchors_never_form_causal_bindings(self):
        observation_ids = {
            row["fast_node_id"]
            for row in self.result["anchors"]
            if row["activation_mode"] == "OBSERVATION_ONLY"
        }
        self.assertEqual(10, len(observation_ids))
        self.assertTrue(
            all(row["anchor_fast_node_id"] not in observation_ids for row in self.result["bindings"])
        )
        self.assertTrue(
            all(
                row["causal_attribution_allowed"] is False
                for row in self.result["anchors"]
                if row["activation_mode"] == "OBSERVATION_ONLY"
            )
        )

    def test_anchor_projection_matches_the_50_0_timeline(self):
        nodes = {row["fast_node_id"]: row for row in self.timeline}
        for anchor in self.result["anchors"]:
            node = nodes[anchor["fast_node_id"]]
            with self.subTest(anchor=anchor["anchor_id"]):
                self.assertEqual(node["fact"], anchor["fact"])
                self.assertEqual(node["occurred_at"], anchor["occurred_at"])
                self.assertEqual(node["first_public_at"], anchor["first_public_at"])
                self.assertEqual(
                    node["occurred_at_precision"], anchor["occurred_at_precision"]
                )
                self.assertEqual(
                    node["first_public_at_precision"],
                    anchor["first_public_at_precision"],
                )


    def test_invalid_direction_lag_and_node_transition_are_rejected(self):
        mutated = copy.deepcopy(self.bindings[:3])
        mutated[0]["expected_path"]["IMMEDIATE"] = "SIDEWAYS"
        mutated[1]["lag"] = {"minimum": "P20D", "maximum": "P1D"}
        mutated[2]["to_node_id"] = "event-99-asset-invalid"
        result = review_bindings(
            timeline_nodes=self.timeline,
            anchors=self.anchors,
            bindings=mutated,
            workbench_events_path=PROJECT_ROOT / "work" / "ten_event_rapid_candidate_v2" / "events",
            reviewed_at="2026-08-01T12:00:00+08:00",
        )
        self.assertEqual(
            ["REJECTED", "REJECTED", "REJECTED"],
            [row["binding_status"] for row in result["bindings"]],
        )

    def test_event_level_mechanism_evidence_does_not_claim_edge_confirmation(self):
        for row in self.result["bindings"]:
            with self.subTest(binding=row["binding_id"]):
                self.assertEqual("EVENT_LEVEL_ONLY", row["edge_support_status"])
                self.assertEqual("NEEDS_HUMAN_REVIEW", row["binding_status"])
    def test_binding_report_failures_are_derived_from_output_content(self):
        clean = binding_hard_failures(
            self.result["anchors"],
            self.result["bindings"],
            self.result["counterevidence_dispositions"],
        )
        self.assertEqual([], clean)

        mutated = copy.deepcopy(self.result)
        mutated["bindings"].pop()
        mutated["bindings"][0]["counterevidence_status"] = "UNLINKED"
        failures = binding_hard_failures(
            mutated["anchors"],
            mutated["bindings"],
            mutated["counterevidence_dispositions"],
        )
        self.assertIn("BINDING_COUNT_MISMATCH", failures)
        self.assertIn("UNRESOLVED_COUNTEREVIDENCE", failures)

    def test_binding_gate_rederives_edge_support_and_disposition_links(self):
        mechanism_sources = _load_mechanism_sources(
            PROJECT_ROOT / "work" / "ten_event_rapid_candidate_v2" / "events"
        )
        mutated = copy.deepcopy(self.result)
        for row in mutated["bindings"]:
            row["binding_status"] = "AI_REVIEWED"
            row["edge_support_status"] = "EXPLICIT_EDGE_SUPPORT"
        mutated["counterevidence_dispositions"].pop()
        failures = binding_hard_failures(
            mutated["anchors"],
            mutated["bindings"],
            mutated["counterevidence_dispositions"],
            mechanism_sources=mechanism_sources,
        )
        self.assertIn("UNTRUSTED_EDGE_SUPPORT_CLAIM", failures)
        self.assertIn("COUNTEREVIDENCE_DISPOSITION_MISMATCH", failures)

    def test_binding_gate_validates_disposition_and_mechanism_evidence(self):
        mechanism_sources = _load_mechanism_sources(
            PROJECT_ROOT / "work" / "ten_event_rapid_candidate_v2" / "events"
        )
        mutated = copy.deepcopy(self.result)
        mutated["bindings"][0].pop("mechanism_evidence")
        mutated["bindings"][0].pop("review")
        disposition = mutated["counterevidence_dispositions"][0]
        disposition["disposition"] = "LINKED"
        disposition["event_id"] = "event-99"
        failures = binding_hard_failures(
            mutated["anchors"],
            mutated["bindings"],
            mutated["counterevidence_dispositions"],
            mechanism_sources=mechanism_sources,
        )
        self.assertIn("COUNTEREVIDENCE_DISPOSITION_INVALID", failures)
        self.assertIn("MECHANISM_EVIDENCE_MISMATCH", failures)
        self.assertIn("BINDING_REVIEW_INVALID", failures)
if __name__ == "__main__":
    unittest.main()
