import hashlib
import tempfile
import unittest
from pathlib import Path

from fingoose_timeline_gap_resolution_v1 import (
    GAP_NODE_IDS,
    evaluate_gap_candidate,
    select_gap_nodes,
    write_gap_resolution_bundle,
)


class TimelineGapResolutionTests(unittest.TestCase):
    def test_selects_exactly_the_eight_fixed_pending_nodes(self):
        nodes = [
            {"fast_node_id": node_id, "evidence_status": "PENDING_EVIDENCE"}
            for node_id in GAP_NODE_IDS
        ]
        nodes.append({"fast_node_id": "fast-event-01-M01", "evidence_status": "VERIFIED_EXISTING"})
        selected = select_gap_nodes(nodes)
        self.assertEqual([row["fast_node_id"] for row in selected], list(GAP_NODE_IDS))

    def test_source_located_times_do_not_pass_independent_verification_gate(self):
        with tempfile.TemporaryDirectory(dir=Path("C:/tmp")) as temp:
            snapshot = Path(temp) / "source.txt"
            snapshot.write_text("Exact fact quote", encoding="utf-8")
            digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()
            node = {
                "fast_node_id": "fast-event-05-M01",
                "event_id": "event-05",
                "fact": "Exact fact quote",
                "evidence_status": "PENDING_EVIDENCE",
                "gap_reason": "SOURCE_PACKAGE_INCOMPLETE",
            }
            audit = {
                "semantic_alignment_target": "fast-event-05-M01",
                "decision": "PENDING",
                "fact_status": "VERIFIED",
                "evidence_quote": "Exact fact quote",
                "evidence_locator": "line 1",
                "snapshot_path": "source.txt",
                "sha256": digest,
                "occurred_at_verification": {"status": "SOURCE_LOCATED", "value": "2023-03-08T22:00:00Z", "locator": "page"},
                "first_public_at_verification": {"status": "SOURCE_LOCATED", "value": "2023-03-08T22:00:00Z", "locator": "page"},
            }
            result = evaluate_gap_candidate(node, audit, audit, Path(temp))
            self.assertTrue(result["snapshot_hash_match"])
            self.assertFalse(result["occurred_at_accepted"])
            self.assertFalse(result["first_public_at_accepted"])
            self.assertFalse(result["promotion_eligible"])
            self.assertIn("INDEPENDENT_OCCURRED_AT_NOT_VERIFIED", result["blocking_reasons"])

    def test_fully_verified_record_can_pass_but_hash_mismatch_blocks_it(self):
        with tempfile.TemporaryDirectory(dir=Path("C:/tmp")) as temp:
            snapshot = Path(temp) / "source.txt"
            snapshot.write_text("Exact fact quote", encoding="utf-8")
            digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()
            node = {
                "fast_node_id": "test-node",
                "event_id": "event-test",
                "fact": "Exact fact quote",
                "evidence_status": "PENDING_EVIDENCE",
                "gap_reason": None,
            }
            audit = {
                "semantic_alignment_target": "test-node",
                "decision": "ACCEPTED",
                "fact_status": "VERIFIED",
                "evidence_quote": "Exact fact quote",
                "evidence_locator": "line 1",
                "snapshot_path": "source.txt",
                "sha256": digest,
                "occurred_at_verification": {"status": "VERIFIED", "value": "2024-01-01T00:00:00Z", "locator": "line 2"},
                "first_public_at_verification": {"status": "VERIFIED", "value": "2024-01-01T00:00:00Z", "locator": "line 3"},
            }
            accepted = evaluate_gap_candidate(node, audit, audit, Path(temp), blocker_override=None)
            self.assertTrue(accepted["promotion_eligible"])
            bad_manifest = {**audit, "sha256": "0" * 64}
            blocked = evaluate_gap_candidate(node, audit, bad_manifest, Path(temp), blocker_override=None)
            self.assertFalse(blocked["promotion_eligible"])
            self.assertIn("SNAPSHOT_HASH_MISMATCH", blocked["blocking_reasons"])

    def test_bundle_never_marks_pending_record_promotable(self):
        row = {
            "gap_resolution_id": "gap-fast-event-05-M01",
            "fast_node_id": "fast-event-05-M01",
            "event_id": "event-05",
            "current_evidence_status": "PENDING_EVIDENCE",
            "promotion_eligible": False,
            "blocking_reasons": ["INDEPENDENT_OCCURRED_AT_NOT_VERIFIED"],
        }
        with tempfile.TemporaryDirectory(dir=Path("C:/tmp")) as temp:
            manifest = write_gap_resolution_bundle(Path(temp) / "bundle", [row])
            self.assertFalse(manifest["formal_ready"])
            self.assertTrue(all(item["sha256"] for item in manifest["files"]))


if __name__ == "__main__":
    unittest.main()
