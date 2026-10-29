import json
import tempfile
import unittest
from pathlib import Path

from fingoose_public_company_price_windows_v1 import (
    build_price_candidate,
    calculate_price_window,
    eastmoney_secid,
    parse_eastmoney_payload,
    write_price_bundle,
)


class EastmoneyAdapterTests(unittest.TestCase):
    def test_maps_a_share_tickers_to_eastmoney_secid(self):
        self.assertEqual(eastmoney_secid("600009.SH"), "1.600009")
        self.assertEqual(eastmoney_secid("002030.SZ"), "0.002030")
        with self.assertRaises(ValueError):
            eastmoney_secid("0700.HK")

    def test_parses_daily_forward_adjusted_k_lines(self):
        payload = {
            "data": {
                "code": "600009",
                "market": 1,
                "name": "上海机场",
                "klines": [
                    "2020-03-10,65.00,66.00,67.00,64.00,100,6600,4.50,1.50,0.98,0.20",
                    "2020-03-11,66.00,63.00,66.50,62.00,120,7560,6.82,-4.55,-3.00,0.24",
                ],
            }
        }
        bars = parse_eastmoney_payload(payload)
        self.assertEqual([row["trade_date"] for row in bars], ["2020-03-10", "2020-03-11"])
        self.assertEqual(bars[1]["close"], 63.0)
        self.assertEqual(bars[1]["volume"], 120.0)


class PriceWindowTests(unittest.TestCase):
    def setUp(self):
        self.bars = [
            {"trade_date": f"2020-03-{day:02d}", "close": float(100 + i)}
            for i, day in enumerate([9, 10, 11, 12, 13, 16, 17, 18, 19, 20, 23, 24, 25, 26, 27, 30, 31])
        ]
        self.bars.extend(
            {"trade_date": f"2020-04-{day:02d}", "close": float(117 + i)}
            for i, day in enumerate([1, 2, 3, 7, 8, 9, 10])
        )

    def test_selects_trading_session_offsets_without_calendar_imputation(self):
        window = calculate_price_window(self.bars, "2020-03-11")
        self.assertEqual(window["T_MINUS_1"]["date"], "2020-03-10")
        self.assertEqual(window["T0"]["date"], "2020-03-11")
        self.assertEqual(window["D1"]["date"], "2020-03-12")
        self.assertEqual(window["D3"]["date"], "2020-03-16")
        self.assertEqual(window["D5"]["date"], "2020-03-18")
        self.assertEqual(window["D20"]["date"], "2020-04-09")
        expected = self.bars[22]["close"] / self.bars[1]["close"] - 1
        self.assertAlmostEqual(window["D20"]["raw_return_from_t_minus_1"], expected)

    def test_keeps_missing_offsets_explicit(self):
        window = calculate_price_window(self.bars[:4], "2020-03-11")
        self.assertEqual(window["D3"]["status"], "MISSING_OBSERVATION")
        self.assertIsNone(window["D20"]["close"])


class CandidateBundleTests(unittest.TestCase):
    def test_writes_hashed_public_vendor_candidate_without_causal_upgrade(self):
        company = {
            "event_id": "event-01",
            "anchor_id": "anchor-fast-event-01-M04",
            "anchor_date": "2020-03-11",
            "company_code": "600009.SH",
            "company_name": "上海机场",
        }
        payload = {
            "data": {
                "code": "600009",
                "market": 1,
                "name": "上海机场",
                "klines": [
                    f"2020-03-{day:02d},1,{100+i},1,1,1,1,1,1,1,1"
                    for i, day in enumerate([9, 10, 11, 12, 13, 16, 17, 18])
                ],
            }
        }
        candidate = build_price_candidate(company, payload, "https://example.test/kline")
        self.assertEqual(candidate["release_tier"], "PUBLIC_VENDOR_CANDIDATE")
        self.assertFalse(candidate["formal_ready"])
        self.assertFalse(candidate["financial_attribution_allowed"])
        self.assertEqual(candidate["adjustment"], "FORWARD_ADJUSTED_FQT_1")

        temp_root = Path("C:/tmp")
        temp_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_root) as temp:
            output = Path(temp) / "bundle"
            manifest = write_price_bundle(output, [candidate], {candidate["price_window_id"]: payload})
            self.assertTrue((output / "company_price_windows.jsonl").exists())
            self.assertTrue((output / "snapshots" / f"{candidate['price_window_id']}.json").exists())
            self.assertFalse(manifest["formal_ready"])
            data = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(all(item["sha256"] for item in data["files"]))


if __name__ == "__main__":
    unittest.main()
