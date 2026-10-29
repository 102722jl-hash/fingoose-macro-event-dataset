from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))
CANDIDATE = ROOT / "work/company_impact_high_quality_v2_candidate"


class BuildCompanyConfounderClosureTests(unittest.TestCase):
    def test_arguments_are_research_readable_and_evidence_linked(self) -> None:
        from build_fingoose_company_confounder_closure_v2 import build_closure

        confounders, arguments = build_closure(ROOT, CANDIDATE)

        self.assertEqual(len(arguments), 30)
        self.assertEqual(len(confounders), 30)
        for row in arguments:
            self.assertGreaterEqual(len(row["argument_zh"]), 250)
            self.assertLessEqual(len(row["argument_zh"]), 600)
            self.assertTrue(row["evidence_ids"] or row["negative_search_audit_id"])
            self.assertTrue(row["section_lineage"])
            self.assertEqual(row["review_status"], "NEEDS_HUMAN_REVIEW")

    def test_clean_never_bypasses_completeness_gate(self) -> None:
        from build_fingoose_company_confounder_closure_v2 import build_closure

        confounders, _ = build_closure(ROOT, CANDIDATE)

        for row in confounders:
            if row["overall_grade"] == "CLEAN":
                self.assertEqual(row["company_confounder_status"], "REVIEWED")
                self.assertEqual(row["suspension_status"], "VERIFIED_TRADING")
                self.assertFalse(row["unresolved_reasons"])
            if row["overall_grade"] in {"MATERIAL", "DOMINANT", "UNRESOLVED"}:
                self.assertEqual(row["score_eligibility"], "CHALLENGE_ONLY")
            self.assertFalse(row["formal_ready"])
            self.assertFalse(row["causal_attribution_allowed"])


if __name__ == "__main__":
    unittest.main()
