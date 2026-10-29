from __future__ import annotations

import shutil
import sys
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


class IndustryImpactV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from fingoose_industry_impact_v2 import load_industry_profiles

        cls.profiles = load_industry_profiles(
            ROOT / "configs/industry_impact_v2/event_industry_profiles.json"
        )

    def test_frozen_pool_has_77_unique_mutually_exclusive_mappings(self) -> None:
        expected = {
            "event-01": {"CORE_DIRECT": 3, "SECOND_ORDER": 3, "CONDITIONAL": 2},
            "event-02": {"CORE_DIRECT": 4, "SECOND_ORDER": 3, "CONDITIONAL": 1},
            "event-03": {"CORE_DIRECT": 3, "SECOND_ORDER": 3, "CONDITIONAL": 2},
            "event-04": {"CORE_DIRECT": 4, "SECOND_ORDER": 2, "CONDITIONAL": 2},
            "event-05": {"CORE_DIRECT": 2, "SECOND_ORDER": 3, "CONDITIONAL": 2},
            "event-06": {"CORE_DIRECT": 1, "SECOND_ORDER": 4, "CONDITIONAL": 2},
            "event-07": {"CORE_DIRECT": 1, "SECOND_ORDER": 3, "CONDITIONAL": 3},
            "event-08": {"CORE_DIRECT": 2, "SECOND_ORDER": 3, "CONDITIONAL": 2},
            "event-09": {"CORE_DIRECT": 3, "SECOND_ORDER": 3, "CONDITIONAL": 2},
            "event-10": {"CORE_DIRECT": 4, "SECOND_ORDER": 3, "CONDITIONAL": 2},
        }
        self.assertEqual(len(self.profiles), 77)
        self.assertEqual(
            len({row["event_industry_mapping_id"] for row in self.profiles}), 77
        )
        self.assertEqual(
            len({(row["event_id"], row["sw1_id"]) for row in self.profiles}), 77
        )
        for event_id, tier_counts in expected.items():
            actual = Counter(
                row["impact_tier"]
                for row in self.profiles
                if row["event_id"] == event_id
            )
            self.assertEqual(dict(actual), tier_counts)

    def test_profiles_keep_historical_taxonomy_and_release_boundary(self) -> None:
        event_01 = [row for row in self.profiles if row["event_id"] == "event-01"]
        later = [row for row in self.profiles if row["event_id"] != "event-01"]
        self.assertTrue(all(row["classification_edition"] == "SW2014" for row in event_01))
        self.assertTrue(all(row["classification_edition"] == "SW2021" for row in later))
        for row in self.profiles:
            self.assertRegex(row["sw1_id"], r"^801\d{3}$")
            self.assertTrue(row["selection_basis_zh"])
            self.assertTrue(row["segment_labels_zh"])
            self.assertFalse(row["price_selection_used"])
            self.assertFalse(row["formal_ready"])
            self.assertEqual(row["review_status"], "NEEDS_HUMAN_REVIEW")

    def test_candidate_builder_emits_six_joinable_layers(self) -> None:
        from fingoose_industry_impact_v2 import build_industry_candidate_bundle
        from fingoose_company_impact_io_v2 import read_jsonl

        output = ROOT / "work/_test_industry_impact_v2"
        if output.exists():
            shutil.rmtree(output)
        try:
            report = build_industry_candidate_bundle(ROOT, output_root=output)
            expected_files = {
                "event_industry_mappings.jsonl",
                "industry_mechanism_chains.jsonl",
                "industry_evidence.jsonl",
                "industry_driver_registry.jsonl",
                "industry_market_windows.jsonl",
                "industry_completion_report.jsonl",
            }
            self.assertTrue(expected_files.issubset({path.name for path in output.iterdir()}))
            mappings = read_jsonl(output / "event_industry_mappings.jsonl")
            chains = read_jsonl(output / "industry_mechanism_chains.jsonl")
            drivers = read_jsonl(output / "industry_driver_registry.jsonl")
            windows = read_jsonl(output / "industry_market_windows.jsonl")
            completions = read_jsonl(output / "industry_completion_report.jsonl")
            ids = {row["event_industry_mapping_id"] for row in mappings}
            self.assertEqual(len(ids), 77)
            self.assertEqual(ids, {row["event_industry_mapping_id"] for row in chains})
            self.assertEqual(ids, {row["event_industry_mapping_id"] for row in drivers})
            self.assertEqual(ids, {row["event_industry_mapping_id"] for row in windows})
            self.assertEqual(ids, {row["event_industry_mapping_id"] for row in completions})
            self.assertTrue(all(len(row["nodes"]) == 7 for row in chains))
            self.assertTrue(all(row["completion_status"] == "OPEN" for row in completions))
            for completion in completions:
                self.assertEqual(
                    set(completion["gate_statuses"]),
                    {
                        "mechanism_evidence",
                        "driver_data",
                        "market_window",
                        "company_sample",
                    },
                )
                self.assertEqual(
                    set(completion["evidence_coverage"]),
                    {
                        "required_node_count",
                        "evidenced_node_count",
                        "missing_node_ids",
                    },
                )
                coverage = completion["evidence_coverage"]
                self.assertEqual(coverage["required_node_count"], 7)
                self.assertEqual(
                    coverage["evidenced_node_count"]
                    + len(coverage["missing_node_ids"]),
                    7,
                )
            for window in windows:
                gap = window["data_availability_gap"]
                self.assertEqual(gap["gap_status"], "OPEN")
                self.assertEqual(
                    gap["reason_codes"],
                    [
                        "SHENWAN_INDEX_HISTORY_NOT_AVAILABLE",
                        "CSI300_HISTORY_NOT_AVAILABLE_IN_LICENSED_DATABASE",
                    ],
                )
                self.assertEqual(
                    gap["availability_audit_id"],
                    "mysql-industry-market-availability-audit-2026-08-04",
                )
                self.assertEqual(
                    window["missing_value_policy"],
                    "KEEP_NULL_NEVER_ZERO_IMPUTE",
                )
            self.assertFalse(report["formal_ready"])
            self.assertEqual(report["sha_gate"], "DEFERRED")
        finally:
            if output.exists():
                shutil.rmtree(output)


if __name__ == "__main__":
    unittest.main()
