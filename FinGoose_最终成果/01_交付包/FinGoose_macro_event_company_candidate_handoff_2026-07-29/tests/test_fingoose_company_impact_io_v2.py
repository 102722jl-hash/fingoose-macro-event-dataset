from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


class CompanyImpactIoTests(unittest.TestCase):
    def test_make_id_is_stable_across_mapping_order(self) -> None:
        from fingoose_company_impact_io_v2 import make_id

        left = make_id(
            "company",
            {"code": "600009.SH", "name": "上海机场"},
        )
        right = make_id(
            "company",
            {"name": "上海机场", "code": "600009.SH"},
        )

        self.assertEqual(left, right)
        self.assertRegex(left, r"^company-[0-9a-f]{16}$")

    def test_jsonl_round_trip_preserves_chinese_and_null(self) -> None:
        from fingoose_company_impact_io_v2 import read_jsonl, write_jsonl

        rows = [{"company_name": "上海机场", "status": None}]
        path = ROOT / ".test-tmp" / "company-impact-io-round-trip.jsonl"
        try:
            write_jsonl(path, rows)

            self.assertEqual(read_jsonl(path), rows)
            self.assertIn("上海机场", path.read_text(encoding="utf-8"))
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
