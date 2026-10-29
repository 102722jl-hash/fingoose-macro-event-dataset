from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))
CANDIDATE = ROOT / "work/company_impact_high_quality_v2_candidate"
WINDOWS = {"T_MINUS_1", "T0", "D1", "D3", "D5", "D20"}


class BuildCompanyTradingAndCounterevidenceTests(unittest.TestCase):
    def test_trading_reviews_cover_six_actual_dates(self) -> None:
        from build_fingoose_company_trading_and_counterevidence_v2 import (
            build_trading_reviews,
        )

        rows = build_trading_reviews(ROOT, CANDIDATE)

        self.assertEqual(len(rows), 30)
        self.assertEqual(len({row["mapping_id"] for row in rows}), 30)
        for row in rows:
            self.assertEqual(set(row["window_reviews"]), WINDOWS)
            for review in row["window_reviews"].values():
                self.assertTrue(review["actual_date"])
                self.assertIn(
                    review["status"],
                    {
                        "VERIFIED_TRADING",
                        "VERIFIED_SUSPENDED",
                        "VERIFIED_RESUMED",
                        "UNRESOLVED",
                    },
                )
                if review["status"] == "VERIFIED_TRADING":
                    self.assertIsNotNone(review["company_observation"])
                    self.assertTrue(review["source_record_id"])
                    self.assertTrue(review["source_url"])

    def test_each_mapping_has_counterevidence_or_negative_search_record(self) -> None:
        from build_fingoose_company_trading_and_counterevidence_v2 import (
            build_counterevidence_reviews,
        )

        rows = build_counterevidence_reviews(ROOT, CANDIDATE)
        mapping_ids = {
            row["mapping_id"]
            for row in __import__(
                "fingoose_company_impact_io_v2"
            ).read_jsonl(CANDIDATE / "event_company_map.jsonl")
        }

        self.assertEqual({row["mapping_id"] for row in rows}, mapping_ids)
        for row in rows:
            self.assertTrue(row["findings"] or row["negative_search_basis"])
            for finding in row["findings"]:
                self.assertTrue(finding["evidence_id"])
                self.assertTrue(finding["original_quote"])
                self.assertTrue(finding["locator"])
                self.assertTrue(finding["source_url"])
                self.assertTrue(finding["affected_horizons"])


if __name__ == "__main__":
    unittest.main()
