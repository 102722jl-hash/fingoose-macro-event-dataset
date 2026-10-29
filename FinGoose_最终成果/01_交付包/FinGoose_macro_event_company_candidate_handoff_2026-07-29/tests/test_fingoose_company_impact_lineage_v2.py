from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


class CompanyImpactLineageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from fingoose_company_impact_io_v2 import read_jsonl

        cls.candidates = read_jsonl(
            ROOT / "data" / "company_candidate_v1" / "candidate_company_registry.jsonl"
        )
        cls.impacts = read_jsonl(
            ROOT
            / "work"
            / "verifiable_evaluation_phase1_v2_candidate"
            / "event_industry_impacts.jsonl"
        )
        cls.anchors = read_jsonl(
            ROOT
            / "work"
            / "verifiable_evaluation_phase1_v2_candidate"
            / "anchor_catalog.jsonl"
        )

    def test_builds_23_unique_companies_and_30_event_pairs(self) -> None:
        from fingoose_company_impact_lineage_v2 import build_registry_and_map

        companies, mappings = build_registry_and_map(
            self.candidates,
            self.impacts,
            self.anchors,
        )

        self.assertEqual(len(companies), 23)
        self.assertEqual(len({row["company_id"] for row in companies}), 23)
        self.assertEqual(len(mappings), 30)
        self.assertEqual(
            len({(row["event_id"], row["company_id"]) for row in mappings}),
            30,
        )

    def test_freezes_candidate_bindings_without_arbitrary_selection(self) -> None:
        from fingoose_company_impact_lineage_v2 import build_registry_and_map

        _, mappings = build_registry_and_map(
            self.candidates,
            self.impacts,
            self.anchors,
        )

        self.assertTrue(
            all(row["lineage_status"] == "GRAPH_LINKED_CANDIDATE" for row in mappings)
        )
        self.assertTrue(all(row["candidate_binding_ids"] for row in mappings))
        self.assertTrue(all(row["binding_id"] is None for row in mappings))
        self.assertTrue(
            all(
                row["binding_selection_status"]
                == "PENDING_COMPANY_MECHANISM_REVIEW"
                for row in mappings
            )
        )
        self.assertTrue(all(row["price_selection_used"] is False for row in mappings))
        self.assertTrue(all(row["selection_cutoff_at"] for row in mappings))

    def test_writes_reparseable_frozen_config(self) -> None:
        from fingoose_company_impact_io_v2 import read_jsonl
        from fingoose_company_impact_lineage_v2 import write_registry_and_map

        output = ROOT / ".test-tmp"
        registry_path = output / "company_registry.jsonl"
        mapping_path = output / "event_company_map.jsonl"
        registry_path.unlink(missing_ok=True)
        mapping_path.unlink(missing_ok=True)
        try:
            counts = write_registry_and_map(
                self.candidates,
                self.impacts,
                self.anchors,
                output,
            )

            self.assertEqual(counts, {"company_count": 23, "mapping_count": 30})
            self.assertEqual(
                len(read_jsonl(registry_path)),
                23,
            )
            self.assertEqual(len(read_jsonl(mapping_path)), 30)
        finally:
            registry_path.unlink(missing_ok=True)
            mapping_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
