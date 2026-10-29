import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from src.evidence import validate_verified_node
from src.io_utils import read_jsonl, write_jsonl


def verified_record(**overrides):
    record = {
        "fast_node_id": "fast-event-10-M01",
        "event_id": "event-10",
        "evidence_status": "VERIFIED_EXISTING",
        "fact": "The memorandum directed a review of reciprocal trade policy.",
        "occurred_at": "2025-01-20",
        "occurred_at_precision": "DATE",
        "occurred_at_evidence": {
            "source_id": "official-eo",
            "locator": "document date",
            "quote": "January 20, 2025",
        },
        "first_public_at": "2025-01-20",
        "first_public_at_precision": "DATE",
        "first_public_at_evidence": {
            "source_id": "official-eo",
            "locator": "document publication date",
            "quote": "January 20, 2025",
        },
        "source_ids": ["official-eo"],
        "evidence": [
            {
                "source_id": "official-eo",
                "source_tier": "A",
                "url": "https://www.whitehouse.gov/presidential-actions/example/",
                "quote": "The Secretary shall review reciprocal trade arrangements.",
                "locator": "section 2(a)",
            }
        ],
        "gap_reason": None,
        "semantic_change": False,
    }
    record.update(overrides)
    return record


class JsonlIoTests(unittest.TestCase):
    def test_jsonl_round_trip_preserves_unicode_and_record_order(self):
        records = [{"id": "一", "value": 1}, {"id": "二", "value": 2}]
        path = PACKAGE_ROOT / "tests" / "_round_trip_records.jsonl"
        try:
            write_jsonl(path, records)
            self.assertEqual(records, read_jsonl(path))
            self.assertTrue(path.read_text(encoding="utf-8").endswith("\n"))
        finally:
            path.unlink(missing_ok=True)

    def test_jsonl_reader_reports_line_number_for_invalid_json(self):
        path = PACKAGE_ROOT / "tests" / "_invalid_records.jsonl"
        try:
            path.write_text('{"ok": true}\nnot-json\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, r"_invalid_records\.jsonl:2"):
                read_jsonl(path)
        finally:
            path.unlink(missing_ok=True)


class VerifiedEvidenceContractTests(unittest.TestCase):
    def test_valid_date_precision_record_has_no_errors(self):
        self.assertEqual([], validate_verified_node(verified_record()))

    def test_date_precision_rejects_invented_midnight_timestamp(self):
        record = verified_record(occurred_at="2025-01-20T00:00:00Z")
        self.assertIn("unsupported occurred_at precision", validate_verified_node(record))

    def test_timestamp_precision_requires_explicit_timezone(self):
        record = verified_record(
            occurred_at="2025-04-09T00:01:00",
            occurred_at_precision="MINUTE",
        )
        self.assertIn("occurred_at timezone is required", validate_verified_node(record))

    def test_verified_record_requires_quote_locator_and_source(self):
        record = verified_record()
        record["evidence"][0]["quote"] = ""
        record["first_public_at_evidence"]["locator"] = None
        record["source_ids"] = []
        errors = validate_verified_node(record)
        self.assertIn("source_ids must be non-empty", errors)
        self.assertIn("evidence[0].quote is required", errors)
        self.assertIn("first_public_at_evidence.locator is required", errors)

    def test_semantic_change_requires_complete_audit_and_downstream_impact(self):
        record = verified_record(semantic_change=True, replacement_audit=None)
        self.assertIn("missing replacement audit", validate_verified_node(record))

        record["replacement_audit"] = {
            "original_fact": "Inventory conditions raised sensitivity.",
            "original_source_ids": ["old-eia"],
            "replacement_fact": record["fact"],
            "replacement_source_ids": ["official-eo"],
            "replacement_reason": "The previous candidate source did not support the node fact.",
            "affected_records": [],
            "review_result": "REVIEWED",
        }
        self.assertIn(
            "replacement audit affected_records must be non-empty",
            validate_verified_node(record),
        )

    def test_pending_record_is_outside_verified_contract(self):
        record = copy.deepcopy(verified_record())
        record["evidence_status"] = "PENDING_EVIDENCE"
        self.assertEqual([], validate_verified_node(record))


if __name__ == "__main__":
    unittest.main()
