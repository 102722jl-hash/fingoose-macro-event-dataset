from __future__ import annotations

import copy
import sys
import shutil
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


class CompanyIndustryClassificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from fingoose_company_impact_io_v2 import read_jsonl

        cls.mappings = read_jsonl(
            ROOT / "configs/company_impact_high_quality_v2/event_company_map.jsonl"
        )
        cls.history = read_jsonl(
            ROOT
            / "configs/company_impact_high_quality_v2"
            / "industry_classification_history_extract.jsonl"
        )

    def _mapping(self, event_id: str, company_code: str) -> dict:
        return next(
            row
            for row in self.mappings
            if row["event_id"] == event_id and row["company_code"] == company_code
        )

    def test_selects_latest_record_active_at_event_without_future_leakage(self) -> None:
        from fingoose_company_industry_classification_v2 import (
            select_asof_history_record,
        )

        records = [
            {"company_code": "600036", "member_valid_from": "2021-07-30", "sw_industry_code": "480301"},
            {"company_code": "600036", "member_valid_from": "2023-01-01", "sw_industry_code": "490101"},
        ]

        selected = select_asof_history_record(records, "600036.SH", "2022-03-16")

        self.assertEqual(selected["member_valid_from"], "2021-07-30")
        self.assertEqual(selected["member_valid_to_exclusive"], "2023-01-01")
        self.assertEqual(selected["sw_industry_code"], "480301")

    def test_known_financial_and_social_service_cases_map_to_l1(self) -> None:
        from fingoose_company_industry_classification_v2 import classify_mapping

        expected = {
            ("event-03", "600036.SH"): ("801780", "银行"),
            ("event-03", "601318.SH"): ("801790", "非银金融"),
            ("event-04", "600754.SH"): ("801210", "社会服务"),
            ("event-08", "601211.SH"): ("801790", "非银金融"),
            ("event-08", "601988.SH"): ("801780", "银行"),
            ("event-09", "300059.SZ"): ("801790", "非银金融"),
        }

        for key, (index_code, name) in expected.items():
            with self.subTest(key=key):
                classification = classify_mapping(
                    self._mapping(*key), self.history
                )
                self.assertEqual(classification["sw_index_code"], index_code)
                self.assertEqual(classification["sw1_id"], index_code)
                self.assertEqual(classification["sw1_name"], name)
                self.assertEqual(classification["classification_level"], "L1")

    def test_event_edition_boundary_is_explicit(self) -> None:
        from fingoose_company_industry_classification_v2 import (
            classification_edition,
            classify_mapping,
        )

        event_01 = classify_mapping(
            self._mapping("event-01", "002030.SZ"), self.history
        )
        event_02 = classify_mapping(
            self._mapping("event-02", "600346.SH"), self.history
        )

        self.assertEqual(event_01["classification_edition"], "SW2014")
        self.assertEqual(event_02["classification_edition"], "SW2021")
        self.assertEqual(classification_edition("2021-07-29"), "SW2014")
        self.assertEqual(classification_edition("2021-07-30"), "SW2021")

    def test_review_rows_have_source_provenance_and_separate_code_namespaces(self) -> None:
        from fingoose_company_industry_classification_v2 import (
            build_classification_reviews,
        )

        reviews, enriched = build_classification_reviews(self.mappings, self.history)

        self.assertEqual(len(reviews), 30)
        self.assertEqual(len(enriched), 30)
        for review in reviews:
            classification = review["industry_classification"]
            self.assertRegex(classification["sw_industry_code"], r"^\d{6}$")
            self.assertRegex(classification["sw_index_code"], r"^801\d{3}$")
            self.assertEqual(
                classification["code_namespace"],
                {
                    "sw_industry_code": "SWS_CLASSIFICATION_6_DIGIT",
                    "sw_index_code": "SWS_L1_BENCHMARK_INDEX",
                },
            )
            self.assertTrue(classification["evidence_locator"].startswith("Sheet1 row "))
            self.assertTrue(classification["source_url"].startswith("https://"))
            self.assertEqual(len(classification["source_snapshot_sha256"]), 64)
            self.assertEqual(classification["classification_status"], "OFFICIAL_HISTORY_ASOF_MATCHED")
            self.assertEqual(classification["historical_effective_date_status"], "VERIFIED_ACTIVE_ASOF")
            self.assertEqual(classification["review_status"], "SOURCE_VERIFIED_RULE_APPLIED")
            self.assertEqual(review["review_boundary"], "RULE_APPLIED_NOT_MANUAL_APPROVAL")

    def test_all_mappings_are_covered_without_changing_stable_identity(self) -> None:
        from fingoose_company_industry_classification_v2 import (
            build_classification_reviews,
        )

        _, enriched = build_classification_reviews(self.mappings, self.history)

        self.assertEqual(len(enriched), 30)
        self.assertEqual(
            [(row["mapping_id"], row["anchor_id"], row["company_id"]) for row in enriched],
            [(row["mapping_id"], row["anchor_id"], row["company_id"]) for row in self.mappings],
        )
        self.assertFalse(
            any(
                row["industry_classification"]["sw1_id"] == "UNKNOWN"
                for row in enriched
            )
        )

    def test_event_asof_consistency_is_hard_checked(self) -> None:
        from fingoose_company_industry_classification_v2 import (
            ClassificationError,
            build_classification_reviews,
        )

        inconsistent = copy.deepcopy(self.mappings)
        inconsistent[1]["selection_cutoff_at"] = "2020-03-12T00:00:00Z"

        with self.assertRaisesRegex(ClassificationError, "EVENT_ASOF_INCONSISTENT"):
            build_classification_reviews(inconsistent, self.history)

    def test_generator_writes_reviews_and_enriched_map(self) -> None:
        from fingoose_company_impact_io_v2 import read_jsonl
        from fingoose_company_industry_classification_v2 import generate

        output = ROOT / "work" / "_test_company_industry_classification_v2"
        if output.exists():
            shutil.rmtree(output)
        try:
            counts = generate(ROOT, output_root=output)

            reviews = read_jsonl(output / "industry_classification_reviews.jsonl")
            mappings = read_jsonl(output / "event_company_map.jsonl")
            self.assertEqual(counts, {"mapping_count": 30, "review_count": 30, "unknown_count": 0})
            self.assertEqual(len(reviews), 30)
            self.assertEqual(len(mappings), 30)
        finally:
            if output.exists():
                shutil.rmtree(output)


if __name__ == "__main__":
    unittest.main()
