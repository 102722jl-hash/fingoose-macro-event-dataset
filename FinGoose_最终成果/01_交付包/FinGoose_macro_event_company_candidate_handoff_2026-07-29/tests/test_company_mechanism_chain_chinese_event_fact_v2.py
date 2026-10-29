from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))
OUTPUT = ROOT / ".test-tmp/company_mechanism_chinese"


class CompanyMechanismChainChineseEventFactTests(unittest.TestCase):
    def test_all_company_chain_event_facts_use_verified_chinese_display_title(self) -> None:
        from build_fingoose_company_mechanism_chains_v2 import build
        from fingoose_company_impact_io_v2 import read_jsonl

        build(ROOT, output=OUTPUT)
        rows = read_jsonl(OUTPUT / "event_company_mechanism_chains.jsonl")

        self.assertEqual(len(rows), 30)
        for row in rows:
            fact = row["nodes"][0]["statement"]
            self.assertRegex(fact, r"[\u4e00-\u9fff]")
            self.assertFalse(re.search(r"\b(assessed|declared|announced)\b", fact, re.I))


if __name__ == "__main__":
    unittest.main()
