from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


def claim() -> dict[str, object]:
    return {
        "claim_id": "claim-company-airport-demand",
        "company_id": "company-example",
        "claim": "公司主营航空性业务。",
        "claim_type": "BUSINESS_EXPOSURE",
    }


def official(
    source_id: str,
    source_class: str,
    published_at: str,
    *,
    precision: str = "DATE",
    document_id: str | None = None,
) -> dict[str, object]:
    return {
        "source_id": source_id,
        "document_id": document_id or source_id,
        "company_id": "company-example",
        "source_class": source_class,
        "source_url": f"https://example.test/{source_id}.pdf",
        "document_title": source_id,
        "issuer": "示例公司",
        "published_at": published_at,
        "published_at_precision": precision,
        "reporting_period": "2021",
        "original_quote": "报告期内公司主营航空性业务。",
        "page_or_section_locator": "page=12",
    }


class CompanyImpactEvidenceTests(unittest.TestCase):
    def test_two_independent_official_documents_verify_claim(self) -> None:
        from fingoose_company_impact_evidence_v2 import evaluate_claim

        result = evaluate_claim(
            claim(),
            [
                official("annual-2021", "ANNUAL_REPORT", "2022-03-30"),
                official(
                    "ir-2021",
                    "COMPANY_IR_RECORD",
                    "2022-04-15T10:00:00+08:00",
                    precision="MINUTE",
                ),
            ],
            selection_cutoff_at="2022-12-01T09:00:00+08:00",
        )

        self.assertEqual(result["verification_status"], "VERIFIED")
        self.assertEqual(result["availability_scope"], "PREDICTION_VISIBLE")
        self.assertEqual(len(result["evidence_source_ids"]), 2)

    def test_duplicate_document_counts_once(self) -> None:
        from fingoose_company_impact_evidence_v2 import evaluate_claim

        source = official(
            "annual-copy-a",
            "ANNUAL_REPORT",
            "2022-03-30",
            document_id="annual-2021",
        )
        duplicate = official(
            "annual-copy-b",
            "ANNUAL_REPORT",
            "2022-03-30",
            document_id="annual-2021",
        )

        result = evaluate_claim(
            claim(),
            [source, duplicate],
            selection_cutoff_at="2022-12-01T09:00:00+08:00",
        )

        self.assertEqual(result["verification_status"], "PARTIALLY_VERIFIED")
        self.assertEqual(len(result["evidence_source_ids"]), 1)

    def test_post_cutoff_source_is_verification_only(self) -> None:
        from fingoose_company_impact_evidence_v2 import evaluate_claim

        result = evaluate_claim(
            claim(),
            [official("annual-2023", "ANNUAL_REPORT", "2023-03-30")],
            selection_cutoff_at="2022-12-01T09:00:00+08:00",
        )

        self.assertEqual(result["availability_scope"], "VERIFICATION_ONLY")
        self.assertEqual(result["prediction_visible_source_ids"], [])

    def test_same_day_date_precision_is_not_assumed_pre_event(self) -> None:
        from fingoose_company_impact_evidence_v2 import evaluate_claim

        result = evaluate_claim(
            claim(),
            [official("same-day", "ANNUAL_REPORT", "2022-12-01")],
            selection_cutoff_at="2022-12-01T09:00:00+08:00",
        )

        self.assertEqual(result["availability_scope"], "VERIFICATION_ONLY")

    def test_missing_locator_is_rejected(self) -> None:
        from fingoose_company_impact_evidence_v2 import evaluate_claim

        source = official("annual-2021", "ANNUAL_REPORT", "2022-03-30")
        source["page_or_section_locator"] = None

        with self.assertRaisesRegex(
            ValueError,
            "MISSING_EVIDENCE_FIELD:page_or_section_locator",
        ):
            evaluate_claim(
                claim(),
                [source],
                selection_cutoff_at="2022-12-01T09:00:00+08:00",
            )


if __name__ == "__main__":
    unittest.main()
