from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))
CANDIDATE = ROOT / "work/company_impact_high_quality_v2_candidate"


class BuildCompanyConfounderSearchAuditsTests(unittest.TestCase):
    def test_search_audits_cover_frozen_scope(self) -> None:
        from build_fingoose_company_confounder_search_audits_v2 import (
            build_audits,
        )

        audits = build_audits(ROOT, CANDIDATE)

        self.assertEqual(len(audits), 30)
        self.assertEqual(len({row["mapping_id"] for row in audits}), 30)
        self.assertEqual(sum(row["title_count"] for row in audits), 455)

    def test_complete_search_requires_all_candidate_bodies_disposed(self) -> None:
        from build_fingoose_company_confounder_search_audits_v2 import (
            build_audits,
        )

        audits = build_audits(ROOT, CANDIDATE)

        for row in audits:
            if row["search_status"] == "COMPLETE":
                self.assertEqual(
                    row["candidate_count"], row["body_reviewed_count"]
                )
                self.assertFalse(row["unresolved_reasons"])
            if row["candidate_count"] == 0:
                self.assertTrue(row["negative_result_basis"])


if __name__ == "__main__":
    unittest.main()
