from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
CONFIG = ROOT / "configs" / "company_impact_high_quality_v2"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


class CompanyOfficialResearchTests(unittest.TestCase):
    def test_target_registry_has_23_unique_companies(self) -> None:
        rows = [
            json.loads(line)
            for line in (CONFIG / "official_report_targets.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]

        self.assertEqual(len(rows), 23)
        self.assertEqual(len({row["company_code"] for row in rows}), 23)
        self.assertTrue(all(row["annual_year"] <= row["interim_year"] for row in rows))

    def test_build_query_fields_uses_company_name_and_periodic_categories(self) -> None:
        from fingoose_company_official_intake_v2 import build_cninfo_query_fields

        fields = build_cninfo_query_fields(
            company_name="上海机场",
            start_date="2018-01-01",
            end_date="2020-03-11",
        )

        self.assertEqual(fields["searchkey"], "上海机场")
        self.assertEqual(fields["seDate"], "2018-01-01~2020-03-11")
        self.assertEqual(
            fields["category"],
            "category_ndbg_szsh;category_bndbg_szsh",
        )
        self.assertEqual(fields["pageSize"], "100")


if __name__ == "__main__":
    unittest.main()
