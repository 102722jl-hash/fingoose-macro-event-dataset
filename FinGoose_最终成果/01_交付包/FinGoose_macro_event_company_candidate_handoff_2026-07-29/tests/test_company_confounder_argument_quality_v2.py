from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))
CANDIDATE = ROOT / "work/company_impact_high_quality_v2_candidate"


class CompanyConfounderArgumentQualityTests(unittest.TestCase):
    def test_arguments_preserve_complete_review_boundary_sentence(self) -> None:
        from build_fingoose_company_confounder_closure_v2 import build_closure

        _, arguments = build_closure(ROOT, CANDIDATE)

        for row in arguments:
            text = row["argument_zh"]
            self.assertLessEqual(len(text), 600)
            self.assertNotIn("NEED结论", text)
            self.assertTrue(
                text.endswith("禁止作确定性因果归因。")
                or text.endswith("拒绝直接归因。")
            )


if __name__ == "__main__":
    unittest.main()
