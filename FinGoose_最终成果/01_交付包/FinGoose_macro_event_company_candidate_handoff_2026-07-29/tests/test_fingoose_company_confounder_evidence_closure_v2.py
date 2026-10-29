from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


class CompanyConfounderEvidenceClosureTests(unittest.TestCase):
    def test_clean_requires_complete_search_body_reviews_and_trading(self) -> None:
        from fingoose_company_confounder_evidence_closure_v2 import derive_grade

        complete = {
            "search_status": "COMPLETE",
            "candidate_count": 0,
            "body_reviewed_count": 0,
            "unresolved_reasons": [],
        }
        trading = {"overall_status": "VERIFIED_TRADING"}

        self.assertEqual(derive_grade(complete, [], trading, []), "CLEAN")
        self.assertEqual(
            derive_grade(
                dict(complete, search_status="INCOMPLETE"), [], trading, []
            ),
            "UNRESOLVED",
        )
        self.assertEqual(
            derive_grade(
                complete, [], {"overall_status": "UNRESOLVED"}, []
            ),
            "UNRESOLVED",
        )

    def test_title_only_candidate_cannot_receive_resolved_grade(self) -> None:
        from fingoose_company_confounder_evidence_closure_v2 import derive_grade

        audit = {
            "search_status": "INCOMPLETE",
            "candidate_count": 1,
            "body_reviewed_count": 0,
            "unresolved_reasons": ["BODY_REVIEW_INCOMPLETE"],
        }
        candidate = {
            "body_review_status": "TITLE_ONLY",
            "relevance_decision": "RELEVANT",
            "severity_candidate": "MATERIAL",
        }

        self.assertEqual(
            derive_grade(
                audit,
                [candidate],
                {"overall_status": "VERIFIED_TRADING"},
                [],
            ),
            "UNRESOLVED",
        )

    def test_relevant_body_review_requires_quote_locator_and_windows(self) -> None:
        from fingoose_company_confounder_evidence_closure_v2 import (
            validate_body_review,
        )

        row = {
            "review_id": "body-review-1",
            "mapping_id": "event-company-1",
            "event_id": "event-01",
            "company_id": "company-1",
            "announcement_id": "123",
            "announcement_title": "公告",
            "source_url": "https://static.cninfo.com.cn/example.pdf",
            "first_public_at": "2020-03-12",
            "body_review_status": "BODY_REVIEWED",
            "body_locator": "page 1, paragraph 2",
            "original_quote": "公司披露了独立经营事项。",
            "confounder_type": "MATERIAL_OPERATION",
            "affected_windows": ["D1", "D3"],
            "relevance_decision": "RELEVANT",
            "severity_candidate": "MATERIAL",
            "mechanism_zh": "该事项可能独立改变盈利预期。",
            "rejection_reason": None,
            "review_status": "NEEDS_HUMAN_REVIEW",
        }

        self.assertEqual(validate_body_review(row), [])
        self.assertIn(
            "ORIGINAL_QUOTE_REQUIRED",
            validate_body_review(dict(row, original_quote=None)),
        )
        self.assertIn(
            "BODY_LOCATOR_REQUIRED",
            validate_body_review(dict(row, body_locator=None)),
        )
        self.assertIn(
            "AFFECTED_WINDOWS_REQUIRED",
            validate_body_review(dict(row, affected_windows=[])),
        )


if __name__ == "__main__":
    unittest.main()
