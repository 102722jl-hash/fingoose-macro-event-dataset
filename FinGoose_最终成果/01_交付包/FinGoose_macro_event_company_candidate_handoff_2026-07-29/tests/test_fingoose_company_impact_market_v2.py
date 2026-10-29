from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


class CompanyImpactMarketTests(unittest.TestCase):
    def test_after_close_rolls_t0_to_next_session(self) -> None:
        from fingoose_company_impact_market_v2 import align_t0

        sessions = ["2022-02-24", "2022-02-25", "2022-02-28"]
        result = align_t0("2022-02-24T17:00:00+08:00", sessions)

        self.assertEqual(result["T0"], "2022-02-25")
        self.assertEqual(result["alignment_reason"], "AFTER_CLOSE_NEXT_SESSION")

    def test_utc_event_is_converted_to_shanghai_before_t0_alignment(self) -> None:
        from fingoose_company_impact_market_v2 import align_t0

        result = align_t0(
            "2020-03-11T16:30:00+00:00",
            ["2020-03-11", "2020-03-12", "2020-03-13"],
            market_timezone="Asia/Shanghai",
        )
        self.assertEqual(result["T0"], "2020-03-12")
        self.assertEqual(result["local_event_at"], "2020-03-12T00:30:00+08:00")
        self.assertEqual(result["alignment_reason"], "PRE_OPEN_SAME_SESSION")

    def test_relative_return_uses_same_dates(self) -> None:
        from fingoose_company_impact_market_v2 import relative_return

        result = relative_return(company=(100.0, 108.0), benchmark=(200.0, 210.0))

        self.assertAlmostEqual(result, 0.08 - 0.05)

    def test_missing_industry_is_not_zero(self) -> None:
        from fingoose_company_impact_market_v2 import build_relative_window

        result = build_relative_window(
            company_window={"start_date": "2022-02-24", "end_date": "2022-03-03", "start_value": 100.0, "end_value": 108.0},
            market_window={"start_date": "2022-02-24", "end_date": "2022-03-03", "start_value": 200.0, "end_value": 210.0},
            industry_window=None,
        )

        self.assertIsNone(result["industry_relative_return"])
        self.assertEqual(result["industry_status"], "DATA_PENDING")

    def test_mismatched_dates_are_rejected(self) -> None:
        from fingoose_company_impact_market_v2 import build_relative_window

        with self.assertRaisesRegex(ValueError, "WINDOW_DATE_MISMATCH"):
            build_relative_window(
                company_window={"start_date": "2022-02-24", "end_date": "2022-03-03", "start_value": 100.0, "end_value": 108.0},
                market_window={"start_date": "2022-02-25", "end_date": "2022-03-03", "start_value": 200.0, "end_value": 210.0},
                industry_window=None,
            )

    def test_projection_uses_exact_company_dates_and_stores_formula_inputs(self) -> None:
        from fingoose_company_impact_market_v2 import build_relative_record

        company_window = {
            "price_window_id": "price-event-02-600346-sh",
            "event_id": "event-02",
            "anchor_id": "anchor-fast-event-02-M03",
            "company_code": "600346.SH",
            "adjustment": "FORWARD_ADJUSTED_FQT_1",
            "observations": {
                "T_MINUS_1": {"date": "2022-02-23", "close": 8.0, "status": "OBSERVED"},
                "T0": {"date": "2022-02-24", "close": 8.8, "status": "OBSERVED"},
            },
        }
        market_bars = {
            "2022-02-23": {"close": 4600.0},
            "2022-02-24": {"close": 4554.0},
        }

        result = build_relative_record(
            company_window,
            market_bars,
            market_benchmark_id="CSI300",
            industry_bars=None,
            industry_benchmark_id=None,
        )

        t0 = result["observations"]["T0"]
        self.assertEqual(t0["start_date"], "2022-02-23")
        self.assertEqual(t0["end_date"], "2022-02-24")
        self.assertEqual(t0["formula_inputs"]["company"], [8.0, 8.8])
        self.assertEqual(t0["formula_inputs"]["market"], [4600.0, 4554.0])
        self.assertAlmostEqual(t0["market_relative_return"], 0.11)
        self.assertIsNone(t0["industry_relative_return"])
        self.assertEqual(t0["industry_status"], "DATA_PENDING")

    def test_projection_does_not_substitute_nearest_benchmark_date(self) -> None:
        from fingoose_company_impact_market_v2 import build_relative_record

        company_window = {
            "price_window_id": "price-event-02-600346-sh",
            "event_id": "event-02",
            "anchor_id": "anchor-fast-event-02-M03",
            "company_code": "600346.SH",
            "adjustment": "FORWARD_ADJUSTED_FQT_1",
            "observations": {
                "T_MINUS_1": {"date": "2022-02-23", "close": 8.0, "status": "OBSERVED"},
                "T0": {"date": "2022-02-24", "close": 8.8, "status": "OBSERVED"},
            },
        }

        result = build_relative_record(
            company_window,
            {"2022-02-23": {"close": 4600.0}},
            market_benchmark_id="CSI300",
            industry_bars=None,
            industry_benchmark_id=None,
        )

        t0 = result["observations"]["T0"]
        self.assertIsNone(t0["market_relative_return"])
        self.assertEqual(t0["market_status"], "DATA_PENDING")
        self.assertEqual(t0["gap_reason"], "MARKET_END_DATE_MISSING")


    def test_market_outputs_require_matching_event_company_and_anchor(self) -> None:
        from fingoose_company_impact_market_v2 import build_market_outputs

        company_window = {
            "price_window_id": "price-event-02-600346-sh",
            "event_id": "event-02",
            "anchor_id": "anchor-fast-event-02-M03",
            "company_code": "600346.SH",
            "adjustment": "FORWARD_ADJUSTED_FQT_1",
            "source_provider": "EASTMONEY_PUBLIC_ENDPOINT",
            "source_url": "https://example.invalid/company",
            "snapshot_path": "snapshots/company.json",
            "source_snapshot_sha256": "abc",
            "observations": {
                "T_MINUS_1": {"date": "2022-02-23", "close": 8.0, "status": "OBSERVED"},
                "T0": {"date": "2022-02-24", "close": 8.8, "status": "OBSERVED"},
            },
        }
        mapping = {
            "mapping_id": "event-company-1",
            "event_id": "event-02",
            "anchor_id": "anchor-fast-event-02-M03",
            "company_id": "company-1",
            "company_code": "600346.SH",
            "industry_classification": {"sw1_id": "801960"},
        }
        market_bars = {
            "2022-02-23": {"close": 4600.0},
            "2022-02-24": {"close": 4554.0},
        }

        result = build_market_outputs([company_window], [mapping], market_bars)

        self.assertEqual(result["validation"]["hard_failures"], [])
        self.assertEqual(len(result["company_market_windows"]), 1)
        self.assertEqual(len(result["relative_return_windows"]), 1)
        self.assertEqual(
            result["company_market_windows"][0]["mapping_id"],
            "event-company-1",
        )
        self.assertEqual(
            result["relative_return_windows"][0]["observations"]["T0"]["market_status"],
            "AVAILABLE",
        )

        mismatched = dict(mapping, anchor_id="anchor-wrong")
        invalid = build_market_outputs([company_window], [mismatched], market_bars)
        self.assertEqual(
            invalid["validation"]["hard_failures"],
            ["WINDOW_LINEAGE_MISMATCH:event-company-1"],
        )


if __name__ == "__main__":
    unittest.main()
