from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


class CompanyImpactConfounderTests(unittest.TestCase):
    def test_missing_bar_does_not_imply_suspension(self) -> None:
        from fingoose_company_impact_confounders_v2 import classify_suspension

        self.assertEqual(
            classify_suspension(missing_bar=True, exchange_notice=None),
            "UNVERIFIED",
        )

    def test_material_unresolved_and_dominant_are_challenge_only(self) -> None:
        from fingoose_company_impact_confounders_v2 import score_eligibility

        for grade in ("MATERIAL", "DOMINANT", "UNRESOLVED"):
            with self.subTest(grade=grade):
                self.assertEqual(score_eligibility(grade), "CHALLENGE_ONLY")

    def test_registered_non_clean_item_requires_evidence_and_windows(self) -> None:
        from fingoose_company_impact_confounders_v2 import validate_confounder

        item = {
            "confounder_id": "conf-1",
            "severity": "MATERIAL",
            "affected_windows": ["D3", "D5"],
            "occurred_at": "2022-02-28",
            "first_public_at": "2022-02-28",
            "source_url": "https://example.invalid/filing",
            "quote": "Company issued a material forecast revision.",
            "locator": "announcement body, paragraph 1",
            "mechanism": "Changes expected earnings independently of the macro event.",
        }
        self.assertEqual(validate_confounder(item), [])
        self.assertIn(
            "SOURCE_URL_REQUIRED",
            validate_confounder(dict(item, source_url=None)),
        )
        self.assertIn(
            "AFFECTED_WINDOWS_REQUIRED",
            validate_confounder(dict(item, affected_windows=[])),
        )

    def test_unresearched_company_record_stays_unresolved(self) -> None:
        from fingoose_company_impact_confounders_v2 import build_company_confounder_record

        record = build_company_confounder_record(
            mapping={"mapping_id": "event-company-1", "event_id": "event-02", "company_id": "company-1"},
            market_window={"suspension_alignment": "UNVERIFIED"},
            registered_confounders=[],
            counterevidence=[],
        )
        self.assertEqual(record["overall_grade"], "UNRESOLVED")
        self.assertEqual(record["score_eligibility"], "CHALLENGE_ONLY")
        self.assertEqual(record["company_confounder_status"], "SEARCH_PENDING")
        self.assertEqual(record["suspension_status"], "UNVERIFIED")
        self.assertEqual(record["counterevidence_status"], "SEARCH_PENDING")


    def test_title_only_candidate_never_becomes_reviewed_confounder(self) -> None:
        from fingoose_company_impact_confounders_v2 import build_company_confounder_record

        candidate = {
            "confounder_id": "conf-1",
            "severity": "UNRESOLVED",
            "affected_windows": ["D3"],
            "occurred_at": "2022-03-01",
            "first_public_at": "2022-03-01",
            "source_url": "https://static.cninfo.com.cn/example.pdf",
            "quote": "Announcement title",
            "locator": "CNINFO announcement title; PDF body review pending",
            "mechanism": "May change valuation independently of the macro event.",
            "review_status": "NEEDS_BODY_REVIEW",
        }
        record = build_company_confounder_record(
            mapping={"mapping_id": "event-company-1", "event_id": "event-02", "company_id": "company-1"},
            market_window={"suspension_alignment": "UNVERIFIED"},
            registered_confounders=[candidate],
            counterevidence=[],
        )

        self.assertEqual(
            record["company_confounder_status"],
            "CANDIDATES_REGISTERED_NEEDS_BODY_REVIEW",
        )
        self.assertEqual(record["overall_grade"], "UNRESOLVED")
        self.assertEqual(record["score_eligibility"], "CHALLENGE_ONLY")


if __name__ == "__main__":
    unittest.main()
