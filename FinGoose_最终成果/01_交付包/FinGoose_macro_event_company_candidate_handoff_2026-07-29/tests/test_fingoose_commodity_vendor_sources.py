import json
import unittest
from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from fingoose_commodity_sources import AdapterError
from fingoose_commodity_vendor_sources import (
    EASTMONEY_ADAPTER_VERSION,
    LOCKED_QUALITY_FLAGS,
    build_eastmoney_url,
    build_vendor_record,
    merge_vendor_revisions,
    parse_eastmoney_klines,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "commodities" / "eastmoney_i_10d.json"
SCHEMA = ROOT / "schemas" / "fingoose_commodity_vendor_main_v0.2.schema.json"
VALIDATOR = Draft202012Validator(
    json.loads(SCHEMA.read_text(encoding="utf-8")),
    format_checker=FormatChecker(),
)
PROVENANCE = {
    "source_id": "eastmoney_i_main_close",
    "source_url": "https://push2his.eastmoney.com/example",
    "provider": "Eastmoney",
    "retrieved_at": "2026-07-23T09:00:00+08:00",
    "snapshot_id": "FGSNAP-" + "A" * 20,
    "content_sha256": "1" * 64,
    "adapter_version": EASTMONEY_ADAPTER_VERSION,
    "license_scope": "unknown",
    "display_allowed": False,
    "redistribution_allowed": False,
}


def payload(*klines):
    return {"data": {"code": "im", "market": 114, "klines": list(klines)}}


class VendorMainSchemaTests(unittest.TestCase):
    def test_valid_record_and_locked_boundaries(self):
        row = {
            "trade_date": "2026-07-22",
            "open": 790,
            "high": 800,
            "low": 785,
            "close": 798,
            "volume": 424570,
            "amount": 33256033280,
        }
        record = build_vendor_record(row, provenance=PROVENANCE)
        VALIDATOR.validate(record)
        invalid_type = {**record, "record_type": "contract_daily"}
        invalid_status = {
            **record,
            "quality": {**record["quality"], "status": "accepted"},
        }
        with self.assertRaises(ValidationError):
            VALIDATOR.validate(invalid_type)
        with self.assertRaises(ValidationError):
            VALIDATOR.validate(invalid_status)


class EastmoneyVendorSourceTests(unittest.TestCase):
    def test_url_is_locked_to_iron_ore_daily_fields(self):
        query = parse_qs(urlparse(build_eastmoney_url("20260709", "20260722")).query)
        self.assertEqual(query["secid"], ["114.im"])
        self.assertEqual(query["klt"], ["101"])
        self.assertEqual(query["beg"], ["20260709"])
        self.assertEqual(query["end"], ["20260722"])
        self.assertEqual(
            query["fields2"],
            ["f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"],
        )

    def test_verified_example_mapping(self):
        rows = parse_eastmoney_klines(
            payload(
                "2025-04-01,775.0,792.0,797.0,770.0,"
                "424570,33256033280,0,0,0,0"
            ),
            retrieved_at="2026-07-23T09:00:00+08:00",
        )
        self.assertEqual(
            rows[0],
            {
                "trade_date": "2025-04-01",
                "open": 775.0,
                "high": 797.0,
                "low": 770.0,
                "close": 792.0,
                "volume": 424570,
                "amount": 33256033280.0,
            },
        )

    def test_fixture_covers_exact_ten_dates(self):
        rows = parse_eastmoney_klines(
            FIXTURE.read_bytes(),
            retrieved_at="2026-07-23T09:00:00+08:00",
        )
        self.assertEqual(len(rows), 10)
        self.assertEqual(rows[0]["trade_date"], "2026-07-09")
        self.assertEqual(rows[-1]["trade_date"], "2026-07-22")
        record = build_vendor_record(rows[0], provenance=PROVENANCE)
        self.assertEqual(record["quality"]["status"], "review_required")
        self.assertEqual(record["quality"]["flags"], list(LOCKED_QUALITY_FLAGS))
        VALIDATOR.validate(record)

    def test_retrieval_day_and_future_are_always_rejected(self):
        for trade_date in ("2026-07-23", "2026-07-24"):
            with self.subTest(trade_date=trade_date):
                with self.assertRaises(AdapterError):
                    parse_eastmoney_klines(
                        payload(
                            f"{trade_date},775,792,797,770,"
                            "424570,33256033280,0,0,0,0"
                        ),
                        retrieved_at="2026-07-23T16:00:00+08:00",
                    )

    def test_wrong_identity_duplicate_bad_ohlc_and_negative_volume_rejected(self):
        cases = [
            {"data": {"code": "other", "market": 114, "klines": []}},
            payload(
                "2025-04-01,775,792,797,770,1,2,0,0,0,0",
                "2025-04-01,775,792,797,770,1,2,0,0,0,0",
            ),
            payload("2025-04-01,775,792,780,770,1,2,0,0,0,0"),
            payload("2025-04-01,775,792,797,770,-1,2,0,0,0,0"),
        ]
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(AdapterError):
                    parse_eastmoney_klines(
                        case,
                        retrieved_at="2026-07-23T09:00:00+08:00",
                    )

    def test_revision_merge_is_idempotent_then_increments(self):
        row = parse_eastmoney_klines(
            payload("2025-04-01,775,792,797,770,1,2,0,0,0,0"),
            retrieved_at="2026-07-23T09:00:00+08:00",
        )[0]
        first = build_vendor_record(row, provenance=PROVENANCE)
        merged = merge_vendor_revisions([], [first])
        same = merge_vendor_revisions(merged, [deepcopy(first)])
        self.assertEqual(len(same), 1)
        revised_provenance = {**PROVENANCE, "content_sha256": "2" * 64}
        changed = build_vendor_record(
            {**row, "close": 793, "high": 798},
            provenance=revised_provenance,
        )
        revised = merge_vendor_revisions(same, [changed])
        self.assertEqual(len(revised), 2)
        self.assertFalse(revised[0]["is_latest"])
        self.assertEqual(revised[1]["revision"], 2)
        self.assertTrue(revised[1]["is_latest"])


if __name__ == "__main__":
    unittest.main()